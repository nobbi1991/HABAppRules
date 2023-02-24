"""Test Light rule."""
import collections
import os
import pathlib
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.light
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system
import tests.common.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.timer
from habapp_rules.actors.light_config import LightConfig, FunctionConfig, BrightnessTimeout


# pylint: disable=protected-access,no-member,too-many-public-methods
class TestLight(unittest.TestCase):
	"""Tests cases for testing Light rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.send_command_mock_patcher.stop)
		self.send_command_mock = self.send_command_mock_patcher.start()

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Light_Switch", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_state", "")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", True)

		self.light_config = LightConfig(
			on=FunctionConfig(day=BrightnessTimeout(True, 5), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 5)),
			pre_off=FunctionConfig(day=BrightnessTimeout(40, 4), night=BrightnessTimeout(40, 4), sleeping=None),
			leaving=FunctionConfig(day=None, night=BrightnessTimeout(40, 10), sleeping=None),
			pre_sleep=FunctionConfig(day=None, night=BrightnessTimeout(10, 20), sleeping=None)
		)
		with unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			self.light = habapp_rules.actors.light.Light("Unittest_Light", ["Unittest_Light_ctr"], "Unittest_Manual", "Unittest_Presence_state", "Unittest_Sleep_state", "Unittest_Day", self.light_config)

	def test_init_with_switch(self):
		"""Test init with switch_item"""
		with self.assertRaises(TypeError), \
				unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			habapp_rules.actors.light.Light("Unittest_Light_Switch", ["Unittest_Light_ctr"], "Unittest_Manual", "Unittest_Presence_state", "Unittest_Sleep_state", "Unittest_Day", self.light_config)

	def get_state_names(self, states: dict, parent_state: str | None = None) -> list[str]:
		"""Helper function to get all state names (also nested states)

		:param states: dict of all states or children states
		:param parent_state: name of parent state, only if it is a nested state machine
		:return: list of all state names
		"""
		state_names = []
		prefix = f"{parent_state}_" if parent_state else ""
		if parent_state:
			states = states["children"]

		for state in states:
			if "children" in state:
				state_names += self.get_state_names(state, state["name"])
			else:
				state_names.append(f"{prefix}{state['name']}")
		return state_names

	def test_create_graph(self):
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "Light_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)  # pragma: no cover

		presence_graph = tests.common.graph_machines.HierarchicalGraphMachineTimer(
			model=self.light,
			states=self.light.states,
			transitions=self.light.trans,
			initial=self.light.state,
			show_conditions=False)

		presence_graph.get_graph().draw(picture_dir / "Light.png", format="png", prog="dot")

		presence_graph.show_conditions = True
		for state_name in self.get_state_names(self.light.states):
			presence_graph.set_state(state_name)
			presence_graph.get_graph(show_roi=True).draw(picture_dir / f"Light_{state_name}.png", format="png", prog="dot")

	def test_get_initial_state(self):
		"""Test if correct initial state will be set."""
		TestCase = collections.namedtuple("TestCase", "light_value, manual_value, sleep_value, presence_value, expected_state")
		test_cases = [
			# state OFF + Manual OFF
			TestCase(0, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			TestCase(0, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			TestCase(0, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			TestCase(0, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			TestCase(0, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			# state OFF + Manual ON
			TestCase(0, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(0, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(0, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(0, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(0, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			# # state ON + Manual OFF
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			TestCase(42, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_presleep"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_presleep"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			TestCase(42, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_presleep"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_presleep"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			# state ON + Manual ON
			TestCase(42, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(42, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(42, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(42, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(42, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),
		]

		with unittest.mock.patch.object(self.light, "_pre_sleep_configured", return_value=True), unittest.mock.patch.object(self.light, "_leaving_configured", return_value=True):
			for test_case in test_cases:
				tests.helper.oh_item.set_state("Unittest_Light", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_value)
				tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_value)

				self.assertEqual(test_case.expected_state, self.light._get_initial_state("default"), test_case)

		with unittest.mock.patch.object(self.light, "_pre_sleep_configured", return_value=False), unittest.mock.patch.object(self.light, "_leaving_configured", return_value=False):
			for test_case in test_cases:
				tests.helper.oh_item.set_state("Unittest_Light", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_value)
				tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_value)

				expected_state = "auto_on" if test_case.expected_state in {"auto_leaving", "auto_presleep"} else test_case.expected_state

				self.assertEqual(expected_state, self.light._get_initial_state("default"), test_case)

		# assert that all combinations of sleeping / presence are tested
		self.assertEqual(2 * 2 * len(habapp_rules.system.SleepState) * len(habapp_rules.system.PresenceState), len(test_cases))

	def test_preoff_configure(self):
		"""Test _pre_off_configured."""
		TestCase = collections.namedtuple("TestCase", "timeout, result")

		test_cases = [
			TestCase(None, False),
			TestCase(0, False),
			TestCase(1, True),
			TestCase(42, True)
		]

		for test_case in test_cases:
			self.light._timeout_pre_off = test_case.timeout
			self.assertEqual(test_case.result, self.light._pre_off_configured())

	def test_leaving_configure(self):
		"""Test _leaving_configured."""
		TestCase = collections.namedtuple("TestCase", "timeout, result")

		test_cases = [
			TestCase(None, False),
			TestCase(0, False),
			TestCase(1, True),
			TestCase(42, True)
		]

		for test_case in test_cases:
			self.light._timeout_leaving = test_case.timeout
			self.assertEqual(test_case.result, self.light._leaving_configured())

	def test_pre_sleep_configured(self):
		"""Test _pre_sleep_configured."""
		TestCase = collections.namedtuple("TestCase", "timeout, prevent, result")

		always_true = unittest.mock.Mock(return_value=True)
		always_false = unittest.mock.Mock(return_value=False)

		test_cases = [
			# no prevent
			TestCase(None, None, False),
			TestCase(0, None, False),
			TestCase(1, None, True),
			TestCase(42, None, True),

			# prevent as item
			TestCase(None, HABApp.openhab.items.SwitchItem("Test", "ON"), False),
			TestCase(0, HABApp.openhab.items.SwitchItem("Test", "ON"), False),
			TestCase(1, HABApp.openhab.items.SwitchItem("Test", "ON"), False),
			TestCase(42, HABApp.openhab.items.SwitchItem("Test", "ON"), False),

			TestCase(None, HABApp.openhab.items.SwitchItem("Test", "OFF"), False),
			TestCase(0, HABApp.openhab.items.SwitchItem("Test", "OFF"), False),
			TestCase(1, HABApp.openhab.items.SwitchItem("Test", "OFF"), True),
			TestCase(42, HABApp.openhab.items.SwitchItem("Test", "OFF"), True),

			# prevent as callable
			TestCase(None, always_true, False),
			TestCase(0, always_true, False),
			TestCase(1, always_true, False),
			TestCase(42, always_true, False),

			TestCase(None, always_false, False),
			TestCase(0, always_false, False),
			TestCase(1, always_false, True),
			TestCase(42, always_false, True)
		]

		for test_case in test_cases:
			self.light._timeout_pre_sleep = test_case.timeout
			self.light._config.pre_sleep_prevent = test_case.prevent
			self.assertEqual(test_case.result, self.light._pre_sleep_configured())

	def test_was_on_before(self):
		"""Test _was_on_before."""
		TestCase = collections.namedtuple("TestCase", "value, result")

		test_cases = [
			TestCase(None, False),
			TestCase(0, False),
			TestCase(1, True),
			TestCase(42, True),
			TestCase(True, True),
			TestCase(False, False)
		]

		for test_case in test_cases:
			self.light._brightness_before = test_case.value
			self.assertEqual(test_case.result, self.light._was_on_before())

	def test_test_set_timeouts(self):
		"""Test _set_timeouts."""
		TestCase = collections.namedtuple("TestCase", "config, day, sleeping, timeout_on, timeout_pre_off, timeout_leaving, timeout_pre_sleep")

		light_config_max = LightConfig(
			on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 2)),
			pre_off=FunctionConfig(day=BrightnessTimeout(40, 4), night=BrightnessTimeout(40, 1), sleeping=None),
			leaving=FunctionConfig(day=None, night=BrightnessTimeout(40, 15), sleeping=None),
			pre_sleep=FunctionConfig(day=None, night=BrightnessTimeout(10, 7), sleeping=None)
		)

		light_config_min = LightConfig(
			on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 2)),
			pre_off=None,
			leaving=None,
			pre_sleep=None
		)

		test_cases = [
			TestCase(light_config_max, False, False, 5, 1, 15, 7),
			TestCase(light_config_max, False, True, 2, None, None, None),
			TestCase(light_config_max, True, False, 10, 4, None, None),
			TestCase(light_config_max, True, True, 2, None, None, None),

			TestCase(light_config_min, False, False, 5, None, None, None),
			TestCase(light_config_min, False, True, 2, None, None, None),
			TestCase(light_config_min, True, False, 10, None, None, None),
			TestCase(light_config_min, True, True, 2, None, None, None),
		]

		for test_case in test_cases:
			self.light._item_day = HABApp.openhab.items.SwitchItem("day", "ON" if test_case.day else "OFF")
			self.light._item_sleeping_state = HABApp.openhab.items.SwitchItem("sleeping", "sleeping" if test_case.sleeping else "awake")
			self.light._config = test_case.config

			self.light._set_timeouts()

			self.assertEqual(test_case.timeout_on, self.light.state_machine.states["auto"].states["on"].timeout)
			self.assertEqual(test_case.timeout_pre_off, self.light.state_machine.states["auto"].states["preoff"].timeout)
			self.assertEqual(test_case.timeout_leaving, self.light.state_machine.states["auto"].states["leaving"].timeout)
			self.assertEqual(test_case.timeout_pre_sleep, self.light.state_machine.states["auto"].states["presleep"].timeout)

	def test_set_brightness(self):
		"""Test _set_brightness."""
		TestCase = collections.namedtuple("TestCase", "input_value, output_value")

		test_cases = [
			TestCase(None, None),
			TestCase(0, 0),
			TestCase(40, 40),
			TestCase(True, "ON"),
			TestCase(False, "OFF")
		]

		for test_case in test_cases:
			with unittest.mock.patch.object(self.light, "_get_target_brightness", return_value=test_case.input_value), unittest.mock.patch.object(self.light._state_observer, "send_command") as send_command_mock:
				self.light._set_brightness()
				if test_case.output_value is None:
					send_command_mock.assert_not_called()
				else:
					send_command_mock.assert_called_with(test_case.output_value)

		# first call after init should not set brightness
		self.light._previous_state = None
		with unittest.mock.patch.object(self.light._state_observer, "send_command") as send_command_mock:
			self.light._set_brightness()
			send_command_mock.assert_not_called()

	def test_get_target_brightness(self):
		"""Test _get_target_brightness."""
		TestCase = collections.namedtuple("TestCase", "state, previous_state, day, sleeping, expected_value")

		light_config = LightConfig(
			on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 2)),
			pre_off=FunctionConfig(day=BrightnessTimeout(40, 4), night=BrightnessTimeout(32, 1), sleeping=None),
			leaving=FunctionConfig(day=None, night=BrightnessTimeout(40, 15), sleeping=None),
			pre_sleep=FunctionConfig(day=None, night=BrightnessTimeout(10, 7), sleeping=None)
		)
		self.light._config = light_config
		self.light._brightness_before = 42
		self.light._state_observer._value = 100
		self.light._state_observer._last_manual_event = HABApp.openhab.events.ItemCommandEvent("Item_name", "ON")

		test_cases = [
			# ============================== auto ON ==============================
			TestCase("auto_on", previous_state="manual", day=False, sleeping=False, expected_value=None),
			TestCase("auto_on", previous_state="manual", day=False, sleeping=True, expected_value=None),
			TestCase("auto_on", previous_state="manual", day=True, sleeping=False, expected_value=None),
			TestCase("auto_on", previous_state="manual", day=True, sleeping=True, expected_value=None),

			TestCase("auto_on", previous_state="auto_preoff", day=False, sleeping=False, expected_value=42),
			TestCase("auto_on", previous_state="auto_preoff", day=False, sleeping=True, expected_value=42),
			TestCase("auto_on", previous_state="auto_preoff", day=True, sleeping=False, expected_value=42),
			TestCase("auto_on", previous_state="auto_preoff", day=True, sleeping=True, expected_value=42),

			TestCase("auto_on", previous_state="auto_off", day=False, sleeping=False, expected_value=80),
			TestCase("auto_on", previous_state="auto_off", day=False, sleeping=True, expected_value=40),
			TestCase("auto_on", previous_state="auto_off", day=True, sleeping=False, expected_value=None),
			TestCase("auto_on", previous_state="auto_off", day=True, sleeping=True, expected_value=40),

			TestCase("auto_on", previous_state="auto_leaving", day=False, sleeping=False, expected_value=42),
			TestCase("auto_on", previous_state="auto_leaving", day=False, sleeping=True, expected_value=42),
			TestCase("auto_on", previous_state="auto_leaving", day=True, sleeping=False, expected_value=42),
			TestCase("auto_on", previous_state="auto_leaving", day=True, sleeping=True, expected_value=42),

			TestCase("auto_on", previous_state="auto_presleep", day=False, sleeping=False, expected_value=42),
			TestCase("auto_on", previous_state="auto_presleep", day=False, sleeping=True, expected_value=42),
			TestCase("auto_on", previous_state="auto_presleep", day=True, sleeping=False, expected_value=42),
			TestCase("auto_on", previous_state="auto_presleep", day=True, sleeping=True, expected_value=42),

			# ============================== auto PRE_OFF ==============================
			TestCase("auto_preoff", previous_state="auto_on", day=False, sleeping=False, expected_value=32),
			TestCase("auto_preoff", previous_state="auto_on", day=False, sleeping=True, expected_value=None),
			TestCase("auto_preoff", previous_state="auto_on", day=True, sleeping=False, expected_value=40),
			TestCase("auto_preoff", previous_state="auto_on", day=True, sleeping=True, expected_value=None),

			# ============================== auto OFF ==============================
			TestCase("auto_off", previous_state="auto_on", day=False, sleeping=False, expected_value=False),
			TestCase("auto_off", previous_state="auto_on", day=False, sleeping=True, expected_value=False),
			TestCase("auto_off", previous_state="auto_on", day=True, sleeping=False, expected_value=False),
			TestCase("auto_off", previous_state="auto_on", day=True, sleeping=True, expected_value=False),

			TestCase("auto_off", previous_state="auto_preoff", day=False, sleeping=False, expected_value=False),
			TestCase("auto_off", previous_state="auto_preoff", day=False, sleeping=True, expected_value=False),
			TestCase("auto_off", previous_state="auto_preoff", day=True, sleeping=False, expected_value=False),
			TestCase("auto_off", previous_state="auto_preoff", day=True, sleeping=True, expected_value=False),

			TestCase("auto_off", previous_state="auto_leaving", day=False, sleeping=False, expected_value=False),
			TestCase("auto_off", previous_state="auto_leaving", day=False, sleeping=True, expected_value=False),
			TestCase("auto_off", previous_state="auto_leaving", day=True, sleeping=False, expected_value=False),
			TestCase("auto_off", previous_state="auto_leaving", day=True, sleeping=True, expected_value=False),

			TestCase("auto_off", previous_state="auto_presleep", day=False, sleeping=False, expected_value=False),
			TestCase("auto_off", previous_state="auto_presleep", day=False, sleeping=True, expected_value=False),
			TestCase("auto_off", previous_state="auto_presleep", day=True, sleeping=False, expected_value=False),
			TestCase("auto_off", previous_state="auto_presleep", day=True, sleeping=True, expected_value=False),

			# ============================== auto leaving ==============================
			TestCase("auto_leaving", previous_state="auto_on", day=False, sleeping=False, expected_value=40),
			TestCase("auto_leaving", previous_state="auto_on", day=False, sleeping=True, expected_value=None),
			TestCase("auto_leaving", previous_state="auto_on", day=True, sleeping=False, expected_value=None),
			TestCase("auto_leaving", previous_state="auto_on", day=True, sleeping=True, expected_value=None),

			TestCase("auto_leaving", previous_state="auto_preoff", day=False, sleeping=False, expected_value=40),
			TestCase("auto_leaving", previous_state="auto_preoff", day=False, sleeping=True, expected_value=None),
			TestCase("auto_leaving", previous_state="auto_preoff", day=True, sleeping=False, expected_value=None),
			TestCase("auto_leaving", previous_state="auto_preoff", day=True, sleeping=True, expected_value=None),

			TestCase("auto_leaving", previous_state="auto_off", day=False, sleeping=False, expected_value=40),
			TestCase("auto_leaving", previous_state="auto_off", day=False, sleeping=True, expected_value=None),
			TestCase("auto_leaving", previous_state="auto_off", day=True, sleeping=False, expected_value=None),
			TestCase("auto_leaving", previous_state="auto_off", day=True, sleeping=True, expected_value=None),

			TestCase("auto_leaving", previous_state="auto_presleep", day=False, sleeping=False, expected_value=40),
			TestCase("auto_leaving", previous_state="auto_presleep", day=False, sleeping=True, expected_value=None),
			TestCase("auto_leaving", previous_state="auto_presleep", day=True, sleeping=False, expected_value=None),
			TestCase("auto_leaving", previous_state="auto_presleep", day=True, sleeping=True, expected_value=None),

			# ============================== auto PRE_SLEEP ==============================
			TestCase("auto_presleep", previous_state="auto_on", day=False, sleeping=False, expected_value=10),
			TestCase("auto_presleep", previous_state="auto_on", day=False, sleeping=True, expected_value=10),
			TestCase("auto_presleep", previous_state="auto_on", day=True, sleeping=False, expected_value=None),
			TestCase("auto_presleep", previous_state="auto_on", day=True, sleeping=True, expected_value=None),

			TestCase("auto_presleep", previous_state="auto_preoff", day=False, sleeping=False, expected_value=10),
			TestCase("auto_presleep", previous_state="auto_preoff", day=False, sleeping=True, expected_value=10),
			TestCase("auto_presleep", previous_state="auto_preoff", day=True, sleeping=False, expected_value=None),
			TestCase("auto_presleep", previous_state="auto_preoff", day=True, sleeping=True, expected_value=None),

			TestCase("auto_presleep", previous_state="auto_off", day=False, sleeping=False, expected_value=10),
			TestCase("auto_presleep", previous_state="auto_off", day=False, sleeping=True, expected_value=10),
			TestCase("auto_presleep", previous_state="auto_off", day=True, sleeping=False, expected_value=None),
			TestCase("auto_presleep", previous_state="auto_off", day=True, sleeping=True, expected_value=None),

			TestCase("auto_presleep", previous_state="auto_leaving", day=False, sleeping=False, expected_value=10),
			TestCase("auto_presleep", previous_state="auto_leaving", day=False, sleeping=True, expected_value=10),
			TestCase("auto_presleep", previous_state="auto_leaving", day=True, sleeping=False, expected_value=None),
			TestCase("auto_presleep", previous_state="auto_leaving", day=True, sleeping=True, expected_value=None),

			TestCase("init", previous_state="does_not_matter", day=False, sleeping=False, expected_value=None),
			TestCase("init", previous_state="does_not_matter", day=False, sleeping=True, expected_value=None),
			TestCase("init", previous_state="does_not_matter", day=True, sleeping=False, expected_value=None),
			TestCase("init", previous_state="does_not_matter", day=True, sleeping=True, expected_value=None)
		]

		for test_case in test_cases:
			self.light._item_sleeping_state.value = habapp_rules.system.SleepState.SLEEPING.value if test_case.sleeping else habapp_rules.system.SleepState.AWAKE.value
			self.light._item_day.value = "ON" if test_case.day else "OFF"
			self.light.state = test_case.state
			self.light._previous_state = test_case.previous_state

			self.assertEqual(test_case.expected_value, self.light._get_target_brightness(), test_case)

		# switch on by value
		for switch_on_value in [20, "INCREASE"]:
			self.light._state_observer._last_manual_event = HABApp.openhab.events.ItemCommandEvent("Item_name", switch_on_value)
			for test_case in test_cases:
				if test_case.state == "auto_on" and test_case.previous_state == "auto_off":
					self.light.state = test_case.state
					self.light._previous_state = test_case.previous_state
					self.assertIsNone(self.light._get_target_brightness())

	def test_auto_off_transitions(self):
		"""Test transitions of auto_off."""
		# to auto_on by hand trigger
		self.light.to_auto_off()
		tests.helper.oh_item.send_command("Unittest_Light", "ON", "OFF")
		self.assertEqual("auto_on", self.light.state)

		# to leaving (configured)
		self.light.to_auto_off()
		with unittest.mock.patch.object(self.light, "_leaving_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_leaving", self.light.state)

		# to leaving (NOT configured)
		self.light.to_auto_off()
		with unittest.mock.patch.object(self.light, "_leaving_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_off", self.light.state)

		# to pre sleep (configured)
		self.light.to_auto_off()
		with unittest.mock.patch.object(self.light, "_pre_sleep_configured", return_value=True), unittest.mock.patch.object(self.light._config.pre_sleep, "day", habapp_rules.actors.light_config.BrightnessTimeout(67, 20)):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_presleep", self.light.state)

		# to pre sleep (NOT configured)
		self.light.to_auto_off()
		with unittest.mock.patch.object(self.light, "_pre_sleep_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_off", self.light.state)

	def test_auto_on_transitions(self):
		"""Test transitions of auto_on."""
		# timer is re triggered by hand_changed
		self.light._state_observer._value = 20
		self.light.to_auto_on()
		self.light.state_machine.states["auto"].states["on"].runner = {}  # remove timer
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.send_command("Unittest_Light", 40, 20)
		self.assertEqual("auto_on", self.light.state)
		next(iter(self.light.state_machine.states["auto"].states["on"].runner.values())).start.assert_called_once()  # check if timer was called

		# to auto_off by hand
		self.light.to_auto_on()
		tests.helper.oh_item.send_command("Unittest_Light", "OFF", "ON")
		self.assertEqual("auto_off", self.light.state)

		# to leaving (configured)
		self.light.to_auto_on()
		with unittest.mock.patch.object(self.light, "_leaving_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_leaving", self.light.state)

		# to leaving (NOT configured)
		self.light.to_auto_on()
		with unittest.mock.patch.object(self.light, "_leaving_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_on", self.light.state)

		# to sleeping (configured)
		self.light.to_auto_on()
		with unittest.mock.patch.object(self.light, "_pre_sleep_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_presleep", self.light.state)

		# to sleeping (NOT configured)
		self.light.to_auto_on()
		with unittest.mock.patch.object(self.light, "_pre_sleep_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_on", self.light.state)

	def test_auto_pre_off_transitions(self):
		"""Test transitions of auto_preoff."""
		event_mock = unittest.mock.MagicMock()
		msg = ""

		# to auto off by timeout
		self.light.to_auto_preoff()
		self.light.preoff_timeout()
		tests.helper.oh_item.item_state_change_event("Unittest_Light", 0.0)
		self.assertEqual("auto_off", self.light.state)

		# to auto on by hand_on
		self.light.to_auto_preoff()
		self.light._cb_hand_on(event_mock, msg)
		self.assertEqual("auto_on", self.light.state)

		# to auto on by hand_off
		self.light.to_auto_preoff()
		self.light._cb_hand_off(event_mock, msg)
		self.assertEqual("auto_on", self.light.state)

		# to leaving (configured)
		self.light.to_auto_preoff()
		with unittest.mock.patch.object(self.light, "_leaving_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_leaving", self.light.state)

		# to leaving (NOT configured)
		self.light.to_auto_preoff()
		with unittest.mock.patch.object(self.light, "_leaving_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_preoff", self.light.state)

		# to sleeping (configured)
		self.light.to_auto_preoff()
		with unittest.mock.patch.object(self.light, "_pre_sleep_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_presleep", self.light.state)

		# to sleeping (NOT configured)
		self.light.to_auto_preoff()
		with unittest.mock.patch.object(self.light, "_pre_sleep_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_preoff", self.light.state)

	def test_auto_pre_sleep(self):
		"""Test transitions of auto_presleep."""
		# to auto_off by hand_off
		self.light.to_auto_presleep()
		self.light._state_observer._value = 20
		tests.helper.oh_item.send_command("Unittest_Light", "OFF", "ON")
		self.assertEqual("auto_off", self.light.state)

		# to auto_off by timeout
		self.light.to_auto_presleep()
		self.light.presleep_timeout()
		self.assertEqual("auto_off", self.light.state)

		# to auto_off by sleep_aborted | was_on_before = False
		self.light.to_auto_presleep()
		with unittest.mock.patch.object(self.light, "_was_on_before", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.SleepState.POST_SLEEPING.value)
		self.assertEqual("auto_off", self.light.state)

		# to auto_on by sleep_aborted | was_on_before = True
		self.light.to_auto_presleep()
		with unittest.mock.patch.object(self.light, "_was_on_before", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.SleepState.POST_SLEEPING.value)
		self.assertEqual("auto_on", self.light.state)

	def test_auto_leaving(self):
		"""Test transitions of auto_presleep."""
		# to auto_off by hand_off
		self.light.to_auto_leaving()
		self.light._state_observer._value = 20
		tests.helper.oh_item.send_command("Unittest_Light", "OFF", "ON")
		self.assertEqual("auto_off", self.light.state)

		# to auto_off by timeout
		self.light.to_auto_leaving()
		self.light.leaving_timeout()
		self.assertEqual("auto_off", self.light.state)

		# to auto_off by sleep_aborted | was_on_before = False
		self.light.to_auto_leaving()
		with unittest.mock.patch.object(self.light, "_was_on_before", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value, habapp_rules.system.PresenceState.LEAVING.value)
		self.assertEqual("auto_off", self.light.state)

		# to auto_on by sleep_aborted | was_on_before = True
		self.light.to_auto_leaving()
		with unittest.mock.patch.object(self.light, "_was_on_before", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value, habapp_rules.system.PresenceState.LEAVING.value)
		self.assertEqual("auto_on", self.light.state)

	def test_manual(self):
		"""Test manual switch."""
		auto_state = self.light.states[1]
		self.assertEqual("auto", auto_state["name"])

		for state_name in [f"auto_{state['name']}" for state in auto_state["children"] if not "init" in state["name"]]:
			eval(f"self.light.to_{state_name}()")  # pylint: disable=eval-used
			self.assertEqual(state_name, self.light.state)
			tests.helper.oh_item.send_command("Unittest_Manual", "ON", "OFF")
			self.assertEqual("manual", self.light.state)
			tests.helper.oh_item.send_command("Unittest_Manual", "OFF", "ON")
			if self.light._item_light:
				self.assertEqual("auto_on", self.light.state)
			else:
				self.assertEqual("auto_off", self.light.state)

	def test_cb_day(self):
		"""Test callback_day."""
		# ON
		with unittest.mock.patch.object(self.light, "_set_timeouts") as set_timeouts_mock:
			tests.helper.oh_item.send_command("Unittest_Day", "ON", "OFF")
			set_timeouts_mock.assert_called_once()

		# OFF
		with unittest.mock.patch.object(self.light, "_set_timeouts") as set_timeouts_mock:
			tests.helper.oh_item.send_command("Unittest_Day", "OFF", "ON")
			set_timeouts_mock.assert_called_once()

	def test_cb_presence(self):
		"""Test callback_presence -> only states where nothing should happen."""
		for state_name in ["presence", "absence", "long_absence"]:
			with unittest.mock.patch.object(self.light, "leaving_started") as started_mock, \
					unittest.mock.patch.object(self.light, "leaving_aborted") as aborted_mock, \
					unittest.mock.patch.object(self.light, "_set_timeouts") as set_timeouts_mock:
				tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState(state_name).value, habapp_rules.system.PresenceState.LEAVING.value)
				set_timeouts_mock.assert_called_once()
				started_mock.assert_not_called()
				aborted_mock.assert_not_called()

	def test_cb_sleeping(self):
		"""Test callback_presence -> only states where nothing should happen."""
		for state_name in ["awake", "sleeping", "post_sleeping", "locked"]:
			with unittest.mock.patch.object(self.light, "sleep_started") as started_mock, \
					unittest.mock.patch.object(self.light, "sleep_aborted") as aborted_mock, \
					unittest.mock.patch.object(self.light, "_set_timeouts") as set_timeouts_mock:
				tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState(state_name).value, habapp_rules.system.SleepState.PRE_SLEEPING.value)
				set_timeouts_mock.assert_called_once()
				started_mock.assert_not_called()
				aborted_mock.assert_not_called()

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
