"""Test Light rule."""
import collections
import os
import pathlib
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.light
import habapp_rules.common.exceptions
import habapp_rules.common.exceptions
import habapp_rules.common.state_machine_rule
import habapp_rules.system
import tests.common.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.timer


# pylint: disable=protected-access
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

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_state", "")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", True)

		light_config = habapp_rules.actors.light.LightConfig(
			on=habapp_rules.actors.light.StateConfig(True, 80, 40, 5, 5, 5),
			pre_off=habapp_rules.actors.light.StateConfig(40, 40, 0, 4, 4, 0),
			leaving=habapp_rules.actors.light.StateConfig(False, 40, 0, 0, 10, 0),
			pre_sleep=habapp_rules.actors.light.StateConfig(0, 10, 0, 0, 20, 0)
		)
		with unittest.mock.patch.object(habapp_rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			self._light = habapp_rules.actors.light.Light("Unittest_Light", ["Unittest_Light_ctr"], "Unittest_Manual", "Unittest_Presence_state", "Unittest_Sleep_state", "Unittest_Day", light_config)

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
			model=self._light,
			states=self._light.states,
			transitions=self._light.trans,
			initial=self._light.state,
			show_conditions=False)

		presence_graph.get_graph().draw(picture_dir / "Light.png", format="png", prog="dot")

		presence_graph.show_conditions = True
		for state_name in self.get_state_names(self._light.states):
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

			# state ON + Manual OFF
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

		# assert that all combinations of sleeping / presence are tested
		self.assertEqual(2 * 2 * len(habapp_rules.system.SleepState) * len(habapp_rules.system.PresenceState), len(test_cases))

		with unittest.mock.patch.object(self._light, "_pre_sleep_configured", return_value=True), unittest.mock.patch.object(self._light, "_leaving_configured", return_value=True):
			for test_case in test_cases:
				tests.helper.oh_item.set_state("Unittest_Light", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_value)
				tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_value)

				self.assertEqual(test_case.expected_state, self._light._get_initial_state("default"), test_case)

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
