"""Test light rules."""
# pylint: disable=too-many-lines
import collections
import os
import pathlib
import sys
import threading
import time
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.light
import habapp_rules.actors.state_observer
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.test_case_base
import tests.helper.timer
from habapp_rules.actors.light_config import LightConfig, LightConfigExtended, FunctionConfig, BrightnessTimeout

LIGHT_CONFIG = LightConfig(
	on=FunctionConfig(day=BrightnessTimeout(True, 5), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 5)),
	pre_off=FunctionConfig(day=BrightnessTimeout(40, 4), night=BrightnessTimeout(40, 4), sleeping=None),
	leaving=FunctionConfig(day=None, night=BrightnessTimeout(40, 10), sleeping=None),
	pre_sleep=FunctionConfig(day=None, night=BrightnessTimeout(10, 20), sleeping=None)
)


def _get_state_names(states: dict, parent_state: str | None = None) -> list[str]:  # pragma: no cover
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
			state_names += _get_state_names(state, state["name"])
		else:
			state_names.append(f"{prefix}{state['name']}")
	return state_names


# pylint: disable=protected-access,no-member,too-many-public-methods
class TestLightBase(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing Light rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Light_Switch", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_2", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_2_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual_2", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_2_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", True)

		with unittest.mock.patch("habapp_rules.actors.light._LightBase.__abstractmethods__", set()), \
				unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")), \
				unittest.mock.patch("habapp_rules.actors.light._LightBase._get_initial_state", return_value="auto_off"):
			self.light_base = habapp_rules.actors.light._LightBase("Unittest_Light", "Unittest_Manual", "Unittest_Presence_state", "Unittest_Day", LIGHT_CONFIG, "Unittest_Sleep_state")
			self.light_base_without_sleep = habapp_rules.actors.light._LightBase("Unittest_Light_2", "Unittest_Manual_2", "Unittest_Presence_state", "Unittest_Day", LIGHT_CONFIG)

		self.light_base._item_light = HABApp.openhab.items.DimmerItem.get_item("Unittest_Light")
		self.light_base_without_sleep._item_light = HABApp.openhab.items.DimmerItem.get_item("Unittest_Light_2")
		self.light_base._state_observer = habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Light", self.light_base._cb_hand_on, self.light_base._cb_hand_off, control_names=["Unittest_Light_ctr"])
		self.light_base_without_sleep._state_observer = habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Light_2", self.light_base._cb_hand_on, self.light_base._cb_hand_off, control_names=["Unittest_Light_ctr"])

	def test__init__(self):
		"""Test __init__."""
		expected_states = [
			{"name": "manual"},
			{"name": "auto", "initial": "init",
			 "children": [
				 {"name": "init"},
				 {"name": "on", "timeout": 10, "on_timeout": "auto_on_timeout"},
				 {"name": "preoff", "timeout": 4, "on_timeout": "preoff_timeout"},
				 {"name": "off"},
				 {"name": "leaving", "timeout": 5, "on_timeout": "leaving_timeout"},
				 {"name": "presleep", "timeout": 5, "on_timeout": "presleep_timeout"}]}]
		self.assertEqual(expected_states, self.light_base.states)

		expected_trans = [
			{"trigger": "manual_on", "source": "auto", "dest": "manual"},
			{"trigger": "manual_off", "source": "manual", "dest": "auto"},
			{"trigger": "hand_on", "source": ["auto_off", "auto_preoff"], "dest": "auto_on"},
			{"trigger": "hand_off", "source": ["auto_on", "auto_leaving", "auto_presleep"], "dest": "auto_off"},
			{"trigger": "hand_off", "source": "auto_preoff", "dest": "auto_on"},
			{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
			{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_off", "unless": "_pre_off_configured"},
			{"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
			{"trigger": "leaving_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
			{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_on", "conditions": "_was_on_before"},
			{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_off", "unless": "_was_on_before"},
			{"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
			{"trigger": "sleep_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"},
			{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_on", "conditions": "_was_on_before"},
			{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_off", "unless": "_was_on_before"},
			{"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"}
		]
		self.assertEqual(expected_trans, self.light_base.trans)

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):  # pragma: no cover
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "Light_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)

		light_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
			model=tests.helper.graph_machines.FakeModel(),
			states=self.light_base.states,
			transitions=self.light_base.trans,
			initial=self.light_base.state,
			show_conditions=False)

		light_graph.get_graph().draw(picture_dir / "Light.png", format="png", prog="dot")

		for state_name in [state for state in _get_state_names(self.light_base.states) if state not in ["auto_init"]]:
			light_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
				model=tests.helper.graph_machines.FakeModel(),
				states=self.light_base.states,
				transitions=self.light_base.trans,
				initial=state_name,
				show_conditions=True)
			light_graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Light_{state_name}.png", format="png", prog="dot")

	@staticmethod
	def get_initial_state_test_cases() -> collections.namedtuple:
		"""Get test cases for initial state tests

		:return: tests cases
		"""
		TestCase = collections.namedtuple("TestCase", "light_value, manual_value, sleep_value, presence_value, expected_state")
		return [
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

	def test_get_initial_state(self):
		"""Test if correct initial state will be set."""
		test_cases = self.get_initial_state_test_cases()

		# pre sleep configured
		with unittest.mock.patch.object(self.light_base, "_pre_sleep_configured", return_value=True), \
				unittest.mock.patch.object(self.light_base, "_leaving_configured", return_value=True), \
				unittest.mock.patch.object(self.light_base_without_sleep, "_pre_sleep_configured", return_value=False), \
				unittest.mock.patch.object(self.light_base_without_sleep, "_leaving_configured", return_value=True):
			for test_case in test_cases:
				tests.helper.oh_item.set_state("Unittest_Light", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Light_2", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual_2", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_value)
				tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_value)

				self.assertEqual(test_case.expected_state, self.light_base._get_initial_state("default"), test_case)

				if (expected_state := test_case.expected_state) == "auto_presleep":
					if test_case.presence_value == habapp_rules.system.PresenceState.LEAVING.value:
						expected_state = "auto_leaving"
					else:
						expected_state = "auto_on"

				self.assertEqual(expected_state, self.light_base_without_sleep._get_initial_state("default"), test_case)

		# pre sleep not configured
		with unittest.mock.patch.object(self.light_base, "_pre_sleep_configured", return_value=False), unittest.mock.patch.object(self.light_base, "_leaving_configured", return_value=False):
			for test_case in test_cases:
				tests.helper.oh_item.set_state("Unittest_Light", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_value)
				tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_value)

				expected_state = "auto_on" if test_case.expected_state in {"auto_leaving", "auto_presleep"} else test_case.expected_state

				self.assertEqual(expected_state, self.light_base._get_initial_state("default"), test_case)

		# assert that all combinations of sleeping / presence are tested
		self.assertEqual(2 * 2 * len(habapp_rules.system.SleepState) * len(habapp_rules.system.PresenceState), len(test_cases))

	def test_preoff_configured(self):
		"""Test _pre_off_configured."""
		TestCase = collections.namedtuple("TestCase", "timeout, result")

		test_cases = [
			TestCase(None, False),
			TestCase(0, False),
			TestCase(1, True),
			TestCase(42, True)
		]

		for test_case in test_cases:
			self.light_base._timeout_pre_off = test_case.timeout
			self.assertEqual(test_case.result, self.light_base._pre_off_configured())

	def test_leaving_configured(self):
		"""Test _leaving_configured."""
		TestCase = collections.namedtuple("TestCase", "timeout, result")

		test_cases = [
			TestCase(None, False),
			TestCase(0, False),
			TestCase(1, True),
			TestCase(42, True)
		]

		for test_case in test_cases:
			self.light_base._timeout_leaving = test_case.timeout
			self.assertEqual(test_case.result, self.light_base._leaving_configured())

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
			self.light_base._timeout_pre_sleep = test_case.timeout
			self.light_base._config.pre_sleep_prevent = test_case.prevent

			self.light_base_without_sleep._timeout_pre_sleep = test_case.timeout
			self.light_base_without_sleep._config.pre_sleep_prevent = test_case.prevent

			self.assertEqual(test_case.result, self.light_base._pre_sleep_configured())
			self.assertFalse(self.light_base_without_sleep._pre_sleep_configured())

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
			self.light_base._brightness_before = test_case.value
			self.assertEqual(test_case.result, self.light_base._was_on_before())

	def test_set_timeouts(self):
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
			self.light_base._item_day = HABApp.openhab.items.SwitchItem("day", "ON" if test_case.day else "OFF")
			self.light_base._item_sleeping_state = HABApp.openhab.items.SwitchItem("sleeping", "sleeping" if test_case.sleeping else "awake")
			self.light_base._config = test_case.config

			self.light_base._set_timeouts()

			self.assertEqual(test_case.timeout_on, self.light_base.state_machine.states["auto"].states["on"].timeout)
			self.assertEqual(test_case.timeout_pre_off, self.light_base.state_machine.states["auto"].states["preoff"].timeout)
			self.assertEqual(test_case.timeout_leaving, self.light_base.state_machine.states["auto"].states["leaving"].timeout)
			self.assertEqual(test_case.timeout_pre_sleep, self.light_base.state_machine.states["auto"].states["presleep"].timeout)

	@staticmethod
	def get_target_brightness_test_cases() -> collections.namedtuple:
		"""Get test cases for target brightness tests.

		:return: test cases
		"""
		TestCase = collections.namedtuple("TestCase", "state, previous_state, day, sleeping, expected_value")
		return [
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
			TestCase("auto_off", previous_state="manual", day=False, sleeping=False, expected_value=None),
			TestCase("auto_off", previous_state="manual", day=False, sleeping=True, expected_value=None),
			TestCase("auto_off", previous_state="manual", day=True, sleeping=False, expected_value=None),
			TestCase("auto_off", previous_state="manual", day=True, sleeping=True, expected_value=None),

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

	def test_get_target_brightness(self):
		"""Test _get_target_brightness."""

		light_config = LightConfig(
			on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 2)),
			pre_off=FunctionConfig(day=BrightnessTimeout(40, 4), night=BrightnessTimeout(32, 1), sleeping=None),
			leaving=FunctionConfig(day=None, night=BrightnessTimeout(40, 15), sleeping=None),
			pre_sleep=FunctionConfig(day=None, night=BrightnessTimeout(10, 7), sleeping=None)
		)
		self.light_base._config = light_config
		self.light_base._brightness_before = 42
		self.light_base._state_observer._value = 100
		self.light_base._state_observer._last_manual_event = HABApp.openhab.events.ItemCommandEvent("Item_name", "ON")

		self.light_base_without_sleep._config = light_config
		self.light_base_without_sleep._brightness_before = 42
		self.light_base_without_sleep._state_observer._value = 100
		self.light_base_without_sleep._state_observer._last_manual_event = HABApp.openhab.events.ItemCommandEvent("Item_name", "ON")

		for test_case in self.get_target_brightness_test_cases():
			self.light_base._item_sleeping_state.value = habapp_rules.system.SleepState.SLEEPING.value if test_case.sleeping else habapp_rules.system.SleepState.AWAKE.value
			self.light_base._item_day.value = "ON" if test_case.day else "OFF"
			self.light_base.state = test_case.state
			self.light_base._previous_state = test_case.previous_state

			self.light_base_without_sleep._item_day.value = "ON" if test_case.day else "OFF"
			self.light_base_without_sleep.state = test_case.state
			self.light_base_without_sleep._previous_state = test_case.previous_state

			self.assertEqual(test_case.expected_value, self.light_base._get_target_brightness(), test_case)

			if test_case.state != "auto_presleep" and test_case.previous_state != "auto_presleep" and not test_case.sleeping:
				self.assertEqual(test_case.expected_value, self.light_base_without_sleep._get_target_brightness(), test_case)

		# switch on by value
		for switch_on_value in [20, "INCREASE"]:
			self.light_base._state_observer._last_manual_event = HABApp.openhab.events.ItemCommandEvent("Item_name", switch_on_value)
			for test_case in self.get_target_brightness_test_cases():
				if test_case.state == "auto_on" and test_case.previous_state == "auto_off":
					self.light_base.state = test_case.state
					self.light_base._previous_state = test_case.previous_state
					self.assertIsNone(self.light_base._get_target_brightness())

	def test_auto_off_transitions(self):
		"""Test transitions of auto_off."""
		# to auto_on by hand trigger
		self.light_base.to_auto_off()
		tests.helper.oh_item.send_command("Unittest_Light", "ON", "OFF")
		self.assertEqual("auto_on", self.light_base.state)

		# to leaving (configured)
		self.light_base.to_auto_off()
		with unittest.mock.patch.object(self.light_base, "_leaving_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_leaving", self.light_base.state)

		# to leaving (NOT configured)
		self.light_base.to_auto_off()
		with unittest.mock.patch.object(self.light_base, "_leaving_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_off", self.light_base.state)

		# to pre sleep (configured)
		self.light_base.to_auto_off()
		with unittest.mock.patch.object(self.light_base, "_pre_sleep_configured", return_value=True), unittest.mock.patch.object(self.light_base._config.pre_sleep, "day", habapp_rules.actors.light_config.BrightnessTimeout(67, 20)):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_presleep", self.light_base.state)

		# to pre sleep (NOT configured)
		self.light_base.to_auto_off()
		with unittest.mock.patch.object(self.light_base, "_pre_sleep_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_off", self.light_base.state)

	def test_auto_on_transitions(self):
		"""Test transitions of auto_on."""
		self.light_base._state_observer._value = 20

		# to auto_off by hand
		self.light_base.to_auto_on()
		tests.helper.oh_item.send_command("Unittest_Light", "OFF", "ON")
		self.assertEqual("auto_off", self.light_base.state)

		# to leaving (configured)
		self.light_base.to_auto_on()
		with unittest.mock.patch.object(self.light_base, "_leaving_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_leaving", self.light_base.state)

		# to leaving (NOT configured)
		self.light_base.to_auto_on()
		with unittest.mock.patch.object(self.light_base, "_leaving_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_on", self.light_base.state)

		# to sleeping (configured)
		self.light_base.to_auto_on()
		with unittest.mock.patch.object(self.light_base, "_pre_sleep_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_presleep", self.light_base.state)

		# to sleeping (NOT configured)
		self.light_base.to_auto_on()
		with unittest.mock.patch.object(self.light_base, "_pre_sleep_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_on", self.light_base.state)

	def test_auto_pre_off_transitions(self):
		"""Test transitions of auto_preoff."""
		event_mock = unittest.mock.MagicMock()

		# to auto off by timeout
		self.light_base.to_auto_preoff()
		self.light_base.preoff_timeout()
		tests.helper.oh_item.item_state_change_event("Unittest_Light", 0.0)
		self.assertEqual("auto_off", self.light_base.state)

		# to auto on by hand_on
		self.light_base.to_auto_preoff()
		self.light_base._cb_hand_on(event_mock)
		self.assertEqual("auto_on", self.light_base.state)

		# to auto on by hand_off
		self.light_base.to_auto_preoff()
		self.light_base._cb_hand_off(event_mock)
		self.assertEqual("auto_on", self.light_base.state)

		# to leaving (configured)
		self.light_base.to_auto_preoff()
		with unittest.mock.patch.object(self.light_base, "_leaving_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_leaving", self.light_base.state)

		# to leaving (NOT configured)
		self.light_base.to_auto_preoff()
		with unittest.mock.patch.object(self.light_base, "_leaving_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_preoff", self.light_base.state)

		# to sleeping (configured)
		self.light_base.to_auto_preoff()
		with unittest.mock.patch.object(self.light_base, "_pre_sleep_configured", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_presleep", self.light_base.state)

		# to sleeping (NOT configured)
		self.light_base.to_auto_preoff()
		with unittest.mock.patch.object(self.light_base, "_pre_sleep_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("auto_preoff", self.light_base.state)

	def test_auto_pre_sleep(self):
		"""Test transitions of auto_presleep."""
		# to auto_off by hand_off
		self.light_base.to_auto_presleep()
		self.light_base._state_observer._value = 20
		tests.helper.oh_item.send_command("Unittest_Light", "OFF", "ON")
		self.assertEqual("auto_off", self.light_base.state)

		# to auto_off by timeout
		self.light_base.to_auto_presleep()
		self.light_base.presleep_timeout()
		self.assertEqual("auto_off", self.light_base.state)

		# to auto_off by sleep_aborted | was_on_before = False
		self.light_base.to_auto_presleep()
		with unittest.mock.patch.object(self.light_base, "_was_on_before", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.SleepState.POST_SLEEPING.value)
		self.assertEqual("auto_off", self.light_base.state)

		# to auto_on by sleep_aborted | was_on_before = True
		self.light_base.to_auto_presleep()
		with unittest.mock.patch.object(self.light_base, "_was_on_before", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.SleepState.POST_SLEEPING.value)
		self.assertEqual("auto_on", self.light_base.state)

	def test_auto_leaving(self):
		"""Test transitions of auto_presleep."""
		# to auto_off by hand_off
		self.light_base.to_auto_leaving()
		self.light_base._state_observer._value = 20
		tests.helper.oh_item.send_command("Unittest_Light", "OFF", "ON")
		self.assertEqual("auto_off", self.light_base.state)

		# to auto_off by timeout
		self.light_base.to_auto_leaving()
		self.light_base.leaving_timeout()
		self.assertEqual("auto_off", self.light_base.state)

		# to auto_off by sleep_aborted | was_on_before = False
		self.light_base.to_auto_leaving()
		with unittest.mock.patch.object(self.light_base, "_was_on_before", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value, habapp_rules.system.PresenceState.LEAVING.value)
		self.assertEqual("auto_off", self.light_base.state)

		# to auto_on by sleep_aborted | was_on_before = True
		self.light_base.to_auto_leaving()
		with unittest.mock.patch.object(self.light_base, "_was_on_before", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value, habapp_rules.system.PresenceState.LEAVING.value)
		self.assertEqual("auto_on", self.light_base.state)

	def test_manual(self):
		"""Test manual switch."""
		auto_state = self.light_base.states[1]
		self.assertEqual("auto", auto_state["name"])

		for item_state in (0, 50, "OFF", "ON"):
			self.light_base._item_light.value = item_state
			for state_name in [f"auto_{state['name']}" for state in auto_state["children"] if not "init" in state["name"]]:
				eval(f"self.light_base.to_{state_name}()")  # pylint: disable=eval-used
				self.assertEqual(state_name, self.light_base.state)
				tests.helper.oh_item.send_command("Unittest_Manual", "ON", "OFF")
				self.assertEqual("manual", self.light_base.state)
				tests.helper.oh_item.send_command("Unittest_Manual", "OFF", "ON")
				if self.light_base._item_light:
					self.assertEqual("auto_on", self.light_base.state)
				else:
					self.assertEqual("auto_off", self.light_base.state)

	def test_cb_day(self):
		"""Test callback_day."""
		# ON
		with unittest.mock.patch.object(self.light_base, "_set_timeouts") as set_timeouts_mock:
			tests.helper.oh_item.send_command("Unittest_Day", "ON", "OFF")
			set_timeouts_mock.assert_called_once()

		# OFF
		with unittest.mock.patch.object(self.light_base, "_set_timeouts") as set_timeouts_mock:
			tests.helper.oh_item.send_command("Unittest_Day", "OFF", "ON")
			set_timeouts_mock.assert_called_once()

	def test_cb_presence(self):
		"""Test callback_presence -> only states where nothing should happen."""
		for state_name in ["presence", "absence", "long_absence"]:
			with unittest.mock.patch.object(self.light_base, "leaving_started") as started_mock, \
					unittest.mock.patch.object(self.light_base, "leaving_aborted") as aborted_mock, \
					unittest.mock.patch.object(self.light_base, "_set_timeouts") as set_timeouts_mock:
				tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState(state_name).value, habapp_rules.system.PresenceState.LEAVING.value)
				set_timeouts_mock.assert_called_once()
				started_mock.assert_not_called()
				aborted_mock.assert_not_called()

	def test_cb_sleeping(self):
		"""Test callback_presence -> only states where nothing should happen."""
		for state_name in ["awake", "sleeping", "post_sleeping", "locked"]:
			with unittest.mock.patch.object(self.light_base, "sleep_started") as started_mock, \
					unittest.mock.patch.object(self.light_base, "sleep_aborted") as aborted_mock, \
					unittest.mock.patch.object(self.light_base, "_set_timeouts") as set_timeouts_mock:
				tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState(state_name).value, habapp_rules.system.SleepState.PRE_SLEEPING.value)
				set_timeouts_mock.assert_called_once()
				started_mock.assert_not_called()
				aborted_mock.assert_not_called()


# pylint: disable=protected-access,no-member,too-many-public-methods

class TestLightSwitch(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing Light rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_Dimmer", 0)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Light", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Light_2", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual_2", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_2_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", True)

		with unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			self.light_switch = habapp_rules.actors.light.LightSwitch("Unittest_Light", "Unittest_Manual", "Unittest_Presence_state", "Unittest_Day", LIGHT_CONFIG, "Unittest_Sleep_state")
			self.light_switch_without_sleep = habapp_rules.actors.light.LightSwitch("Unittest_Light_2", "Unittest_Manual_2", "Unittest_Presence_state", "Unittest_Day", LIGHT_CONFIG)

	def test_init_with_dimmer(self):
		"""Test init with switch_item"""
		with self.assertRaises(TypeError), \
				unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			habapp_rules.actors.light.LightSwitch("Unittest_Light_Dimmer", "Unittest_Manual", "Unittest_Presence_state", "Unittest_Day", LIGHT_CONFIG, "Unittest_Sleep_state")

	def test__init__(self):
		"""Test __init__."""
		expected_states = [
			{"name": "manual"},
			{"name": "auto", "initial": "init",
			 "children": [
				 {"name": "init"},
				 {"name": "on", "timeout": 10, "on_timeout": "auto_on_timeout"},
				 {"name": "preoff", "timeout": 4, "on_timeout": "preoff_timeout"},
				 {"name": "off"},
				 {"name": "leaving", "timeout": 5, "on_timeout": "leaving_timeout"},
				 {"name": "presleep", "timeout": 5, "on_timeout": "presleep_timeout"}]}]
		self.assertEqual(expected_states, self.light_switch.states)

		expected_trans = [
			{"trigger": "manual_on", "source": "auto", "dest": "manual"},
			{"trigger": "manual_off", "source": "manual", "dest": "auto"},
			{"trigger": "hand_on", "source": ["auto_off", "auto_preoff"], "dest": "auto_on"},
			{"trigger": "hand_off", "source": ["auto_on", "auto_leaving", "auto_presleep"], "dest": "auto_off"},
			{"trigger": "hand_off", "source": "auto_preoff", "dest": "auto_on"},
			{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
			{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_off", "unless": "_pre_off_configured"},
			{"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
			{"trigger": "leaving_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
			{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_on", "conditions": "_was_on_before"},
			{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_off", "unless": "_was_on_before"},
			{"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
			{"trigger": "sleep_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"},
			{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_on", "conditions": "_was_on_before"},
			{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_off", "unless": "_was_on_before"},
			{"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"}
		]
		self.assertEqual(expected_trans, self.light_switch.trans)

	def test_set_light_state(self):
		"""Test _set_brightness."""
		TestCase = collections.namedtuple("TestCase", "input_value, output_value")

		test_cases = [
			TestCase(None, None),
			TestCase(0, "OFF"),
			TestCase(40, "ON"),
			TestCase(True, "ON"),
			TestCase(False, "OFF")
		]

		for test_case in test_cases:
			with unittest.mock.patch.object(self.light_switch, "_get_target_brightness", return_value=test_case.input_value), unittest.mock.patch.object(self.light_switch._state_observer, "send_command") as send_command_mock:
				self.light_switch._set_light_state()
				if test_case.output_value is None:
					send_command_mock.assert_not_called()
				else:
					send_command_mock.assert_called_with(test_case.output_value)

		# first call after init should not set brightness
		self.light_switch._previous_state = None
		with unittest.mock.patch.object(self.light_switch._state_observer, "send_command") as send_command_mock:
			self.light_switch._set_light_state()
			send_command_mock.assert_not_called()

	def test_update_openhab_state(self):
		"""Test _update_openhab_state"""
		states = _get_state_names(self.light_switch.states)

		# test auto_preoff state with timeout <= 60
		self.light_switch.state_machine.set_state("auto_preoff")
		mock_thread_1 = unittest.mock.MagicMock()
		mock_thread_2 = unittest.mock.MagicMock()
		self.light_switch.state_machine.get_state("auto_preoff").timeout = 60

		with unittest.mock.patch("threading.Thread", side_effect=[mock_thread_1, mock_thread_2]) as thread_mock:
			self.light_switch._update_openhab_state()

		thread_mock.assert_called_once_with(target=self.light_switch._LightSwitch__trigger_warning, args=("auto_preoff", 0, 1), daemon=True)
		mock_thread_1.start.assert_called_once()
		mock_thread_2.start.assert_not_called()

		# test auto_preoff state with timeout > 60
		mock_thread_1 = unittest.mock.MagicMock()
		mock_thread_2 = unittest.mock.MagicMock()
		self.light_switch.state_machine.get_state("auto_preoff").timeout = 61

		with unittest.mock.patch("threading.Thread", side_effect=[mock_thread_1, mock_thread_2]) as thread_mock:
			self.light_switch._update_openhab_state()

		thread_mock.assert_has_calls([
			unittest.mock.call(target=self.light_switch._LightSwitch__trigger_warning, args=("auto_preoff", 0, 1), daemon=True),
			unittest.mock.call(target=self.light_switch._LightSwitch__trigger_warning, args=("auto_preoff", 30.5, 2), daemon=True)
		])
		mock_thread_1.start.assert_called_once()
		mock_thread_2.start.assert_called_once()

		# test all other states
		for state in [state_name for state_name in states if state_name != "auto_preoff"]:
			with unittest.mock.patch("threading.Thread") as thread_mock:
				self.light_switch.state_machine.set_state(state)
				self.light_switch._update_openhab_state()
				thread_mock.assert_not_called()

	def test_trigger_warning(self):
		"""Test __trigger_warning."""
		TestCase = collections.namedtuple("TestCase", "state_name, wait_time, switch_off_amount, real_state")
		test_cases = [
			TestCase("auto_preoff", 0, 0, "auto_preoff"),
			TestCase("auto_preoff", 0, 1, "auto_preoff"),
			TestCase("auto_preoff", 0, 2, "auto_preoff"),
			TestCase("auto_preoff", 10, 0, "auto_preoff"),
			TestCase("auto_preoff", 10, 1, "auto_preoff"),
			TestCase("auto_preoff", 10, 2, "auto_preoff"),
			TestCase("auto_preoff", 10, 2, "auto_off"),
		]

		with unittest.mock.patch("time.sleep", spec=time.sleep) as sleep_mock, unittest.mock.patch.object(self.light_switch._state_observer, "send_command") as send_mock:
			for test_case in test_cases:
				sleep_mock.reset_mock()
				send_mock.reset_mock()

				self.light_switch.state_machine.set_state(test_case.real_state)
				self.light_switch._LightSwitch__trigger_warning(test_case.state_name, test_case.wait_time, test_case.switch_off_amount)

				if test_case.state_name == test_case.real_state:
					sleep_calls = []
					on_off_calls = []

					if test_case.wait_time:
						sleep_calls.append(unittest.mock.call(test_case.wait_time))
					for idx in range(test_case.switch_off_amount):
						sleep_calls.append(unittest.mock.call(0.2))
						on_off_calls.append(unittest.mock.call("OFF"))
						on_off_calls.append(unittest.mock.call("ON"))
						if idx + 1 < test_case.switch_off_amount:
							sleep_calls.append(unittest.mock.call(0.5))

					sleep_mock.assert_has_calls(sleep_calls)
					send_mock.assert_has_calls(on_off_calls)
				else:
					send_mock.assert_not_called()

		# state changes after OFF was sent
		with unittest.mock.patch("time.sleep", spec=time.sleep), \
				unittest.mock.patch.object(self.light_switch._state_observer, "send_command") as send_mock, \
				unittest.mock.patch.object(self.light_switch, "state") as state_mock:
			state_mock.__ne__.side_effect = [False, True]

			self.light_switch._LightSwitch__trigger_warning("auto_preoff", 0, 1)

			send_mock.assert_called_once_with("OFF")


# pylint: disable=protected-access,no-member,too-many-public-methods
class TestLightDimmer(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing Light rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Light_Switch", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_2", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_2_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual_2", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_2_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", True)

		with unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			self.light_dimmer = habapp_rules.actors.light.LightDimmer("Unittest_Light", ["Unittest_Light_ctr"], "Unittest_Manual", "Unittest_Presence_state", "Unittest_Day", LIGHT_CONFIG, "Unittest_Sleep_state")
			self.light_dimmer_without_sleep = habapp_rules.actors.light.LightDimmer("Unittest_Light_2", ["Unittest_Light_2_ctr"], "Unittest_Manual_2", "Unittest_Presence_state", "Unittest_Day", LIGHT_CONFIG)

	def test_init_with_switch(self):
		"""Test init with switch_item"""
		with self.assertRaises(TypeError), \
				unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			habapp_rules.actors.light.LightDimmer("Unittest_Light_Switch", ["Unittest_Light_ctr"], "Unittest_Manual", "Unittest_Presence_state", "Unittest_Day", LIGHT_CONFIG, "Unittest_Sleep_state")

	def test__init__(self):
		"""Test __init__."""
		expected_states = [
			{"name": "manual"},
			{"name": "auto", "initial": "init",
			 "children": [
				 {"name": "init"},
				 {"name": "on", "timeout": 10, "on_timeout": "auto_on_timeout"},
				 {"name": "preoff", "timeout": 4, "on_timeout": "preoff_timeout"},
				 {"name": "off"},
				 {"name": "leaving", "timeout": 5, "on_timeout": "leaving_timeout"},
				 {"name": "presleep", "timeout": 5, "on_timeout": "presleep_timeout"}]}]
		self.assertEqual(expected_states, self.light_dimmer.states)

		expected_trans = [
			{"trigger": "manual_on", "source": "auto", "dest": "manual"},
			{"trigger": "manual_off", "source": "manual", "dest": "auto"},
			{"trigger": "hand_on", "source": ["auto_off", "auto_preoff"], "dest": "auto_on"},
			{"trigger": "hand_off", "source": ["auto_on", "auto_leaving", "auto_presleep"], "dest": "auto_off"},
			{"trigger": "hand_off", "source": "auto_preoff", "dest": "auto_on"},
			{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
			{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_off", "unless": "_pre_off_configured"},
			{"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
			{"trigger": "leaving_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
			{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_on", "conditions": "_was_on_before"},
			{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_off", "unless": "_was_on_before"},
			{"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
			{"trigger": "sleep_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"},
			{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_on", "conditions": "_was_on_before"},
			{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_off", "unless": "_was_on_before"},
			{"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"},
			{"trigger": "hand_changed", "source": "auto_on", "dest": "auto_on"}
		]
		self.assertEqual(expected_trans, self.light_dimmer.trans)

	def test_set_light_state(self):
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
			with unittest.mock.patch.object(self.light_dimmer, "_get_target_brightness", return_value=test_case.input_value), unittest.mock.patch.object(self.light_dimmer._state_observer, "send_command") as send_command_mock:
				self.light_dimmer._set_light_state()
				if test_case.output_value is None:
					send_command_mock.assert_not_called()
				else:
					send_command_mock.assert_called_with(test_case.output_value)

		# first call after init should not set brightness
		self.light_dimmer._previous_state = None
		with unittest.mock.patch.object(self.light_dimmer._state_observer, "send_command") as send_command_mock:
			self.light_dimmer._set_light_state()
			send_command_mock.assert_not_called()

	def test_auto_on_transitions(self):
		"""Test transitions of auto_on."""
		# timer is re-triggered by hand_changed if value change > 5
		self.light_dimmer._state_observer._value = 20
		self.light_dimmer.to_auto_on()
		self.light_dimmer.state_machine.states["auto"].states["on"].runner = {}  # remove timer
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.send_command("Unittest_Light", 26, 20)
		self.assertEqual("auto_on", self.light_dimmer.state)
		next(iter(self.light_dimmer.state_machine.states["auto"].states["on"].runner.values())).start.assert_called_once()  # check if timer was called

		# timer is NOT re-triggered by hand_changed if value change <= 5
		self.light_dimmer._state_observer._value = 20
		self.light_dimmer.to_auto_on()
		self.light_dimmer.state_machine.states["auto"].states["on"].runner = {}  # remove timer
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.send_command("Unittest_Light", 25, 20)
		self.assertEqual("auto_on", self.light_dimmer.state)
		self.assertTrue(not self.light_dimmer.state_machine.states["auto"].states["on"].runner)  # check if timer was NOT called


class TestLightExtended(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing LightExtended rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Light_Switch", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_2", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_2_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual_2", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_2_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", True)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door_1", "CLOSED")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door_2", "CLOSED")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion", False)

		self.light_config = LightConfigExtended(
			on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 8), sleeping=BrightnessTimeout(20, 6)),
			pre_off=FunctionConfig(day=BrightnessTimeout(50, 7), night=BrightnessTimeout(40, 6), sleeping=BrightnessTimeout(10, 5)),
			leaving=FunctionConfig(day=BrightnessTimeout(False, 4), night=BrightnessTimeout(50, 10), sleeping=None),
			pre_sleep=FunctionConfig(None, night=BrightnessTimeout(30, 7), sleeping=None),
			motion=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 8), sleeping=BrightnessTimeout(20, 6)),
			door=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 8), sleeping=None)
		)

		with unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			self.light_extended = habapp_rules.actors.light.LightDimmerExtended("Unittest_Light", ["Unittest_Light_ctr"], "Unittest_Manual", "Unittest_Presence_state", "Unittest_Day", self.light_config, "Unittest_Sleep_state", "Unittest_Motion",
			                                                                    ["Unittest_Door_1", "Unittest_Door_2"])
			self.light_extended_2 = habapp_rules.actors.light.LightDimmerExtended("Unittest_Light_2", ["Unittest_Light_2_ctr"], "Unittest_Manual", "Unittest_Presence_state", "Unittest_Day", self.light_config, "Unittest_Sleep_state")

	def test__init__(self):
		"""Test __init__."""
		expected_states = [
			{"name": "manual"},
			{"name": "auto", "initial": "init",
			 "children": [
				 {"name": "init"},
				 {"name": "on", "timeout": 10, "on_timeout": "auto_on_timeout"},
				 {"name": "preoff", "timeout": 4, "on_timeout": "preoff_timeout"},
				 {"name": "off"},
				 {"name": "leaving", "timeout": 5, "on_timeout": "leaving_timeout"},
				 {"name": "presleep", "timeout": 5, "on_timeout": "presleep_timeout"},
				 {"name": "door", "timeout": 999, "on_timeout": "door_timeout"},
				 {"name": "motion", "timeout": 999, "on_timeout": "motion_timeout"}]}]
		self.assertEqual(expected_states, self.light_extended.states)

		expected_trans = [
			{"trigger": "manual_on", "source": "auto", "dest": "manual"},
			{"trigger": "manual_off", "source": "manual", "dest": "auto"},
			{"trigger": "hand_on", "source": ["auto_off", "auto_preoff"], "dest": "auto_on"},
			{"trigger": "hand_off", "source": ["auto_on", "auto_leaving", "auto_presleep"], "dest": "auto_off"},
			{"trigger": "hand_off", "source": "auto_preoff", "dest": "auto_on"},
			{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
			{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_off", "unless": "_pre_off_configured"},
			{"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
			{"trigger": "leaving_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
			{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_on", "conditions": "_was_on_before"},
			{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_off", "unless": "_was_on_before"},
			{"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
			{"trigger": "sleep_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"},
			{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_on", "conditions": "_was_on_before"}, {"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_off", "unless": "_was_on_before"},
			{"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"},
			{"trigger": "hand_changed", "source": "auto_on", "dest": "auto_on"},
			{"trigger": "motion_on", "source": "auto_door", "dest": "auto_motion", "conditions": "_motion_configured"},
			{"trigger": "motion_on", "source": "auto_off", "dest": "auto_motion", "conditions": ["_motion_configured", "_motion_door_allowed"]},
			{"trigger": "motion_on", "source": "auto_preoff", "dest": "auto_motion", "conditions": "_motion_configured"},
			{"trigger": "motion_off", "source": "auto_motion", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
			{"trigger": "motion_off", "source": "auto_motion", "dest": "auto_off", "unless": "_pre_off_configured"},
			{"trigger": "motion_timeout", "source": "auto_motion", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
			{"trigger": "motion_timeout", "source": "auto_motion", "dest": "auto_off", "unless": "_pre_off_configured"},
			{"trigger": "hand_off", "source": "auto_motion", "dest": "auto_off"},
			{"trigger": "door_opened", "source": "auto_off", "dest": "auto_door", "conditions": ["_door_configured", "_motion_door_allowed"]},
			{"trigger": "door_timeout", "source": "auto_door", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
			{"trigger": "door_timeout", "source": "auto_door", "dest": "auto_off", "unless": "_pre_off_configured"},
			{"trigger": "door_closed", "source": "auto_leaving", "dest": "auto_off", "conditions": "_door_off_leaving_configured"},
			{"trigger": "hand_off", "source": "auto_door", "dest": "auto_off"},
			{"trigger": "leaving_started", "source": ["auto_motion", "auto_door"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
			{"trigger": "sleep_started", "source": ["auto_motion", "auto_door"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"}
		]

		self.assertEqual(expected_trans, self.light_extended.trans)
		self.assertEqual(expected_trans, self.light_extended_2.trans)

	def test__init_switch(self):
		"""Test init of switch"""
		with unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			light_extended_switch = habapp_rules.actors.light.LightSwitchExtended("Unittest_Light_Switch", "Unittest_Manual", "Unittest_Presence_state", "Unittest_Day", self.light_config, "Unittest_Sleep_state", "Unittest_Motion",
			                                                                      ["Unittest_Door_1", "Unittest_Door_2"])

			self.assertEqual("Unittest_Light_Switch", light_extended_switch._item_light.name)
			self.assertEqual("Unittest_Manual", light_extended_switch._item_manual.name)
			self.assertEqual("Unittest_Presence_state", light_extended_switch._item_presence_state.name)
			self.assertEqual("Unittest_Day", light_extended_switch._item_day.name)
			self.assertEqual("Unittest_Sleep_state", light_extended_switch._item_sleeping_state.name)
			self.assertEqual("Unittest_Motion", light_extended_switch._item_motion.name)
			self.assertEqual(["Unittest_Door_1", "Unittest_Door_2"], [item.name for item in light_extended_switch._items_door])
			self.assertEqual(self.light_config, light_extended_switch._config)

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):  # pragma: no cover
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "LightExtended_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)

		light_extended_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
			model=self.light_extended,
			states=self.light_extended.states,
			transitions=self.light_extended.trans,
			initial=self.light_extended.state,
			show_conditions=False)

		light_extended_graph.get_graph().draw(picture_dir / "LightExtended.png", format="png", prog="dot")

		for state_name in ["auto_door", "auto_motion", "auto_leaving"]:
			light_extended_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
				model=tests.helper.graph_machines.FakeModel(),
				states=self.light_extended.states,
				transitions=self.light_extended.trans,
				initial=self.light_extended.state,
				show_conditions=True)

			light_extended_graph.set_state(state_name)
			light_extended_graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"LightExtended_{state_name}.png", format="png", prog="dot")

	def test_get_initial_state(self):
		"""Test _get_initial_state."""
		test_cases = TestLightBase.get_initial_state_test_cases()

		# no motion
		with unittest.mock.patch.object(self.light_extended, "_pre_sleep_configured", return_value=True), \
				unittest.mock.patch.object(self.light_extended, "_leaving_configured", return_value=True):
			for test_case in test_cases:
				tests.helper.oh_item.set_state("Unittest_Light", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Light_2", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual_2", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_value)
				tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_value)

				self.assertEqual(test_case.expected_state, self.light_extended._get_initial_state("default"), test_case)
				self.assertEqual(test_case.expected_state, self.light_extended_2._get_initial_state("default"), test_case)

		# motion active
		TestCase = collections.namedtuple("TestCase", "light_value, manual_value, sleep_value, presence_value, expected_state")
		additional_test_cases = [
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
		]

		tests.helper.oh_item.set_state("Unittest_Motion", "ON")
		with unittest.mock.patch.object(self.light_extended, "_pre_sleep_configured", return_value=True), \
				unittest.mock.patch.object(self.light_extended, "_leaving_configured", return_value=True):
			for test_case in additional_test_cases:
				tests.helper.oh_item.set_state("Unittest_Light", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Light_2", test_case.light_value)
				tests.helper.oh_item.set_state("Unittest_Manual_2", test_case.manual_value)
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_value)
				tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_value)

				self.assertEqual("auto_motion", self.light_extended._get_initial_state("default"), test_case)
				self.assertEqual("auto_on", self.light_extended_2._get_initial_state("default"), test_case)

	def test_set_timeouts(self):
		"""Test _set_timeouts."""
		TestCase = collections.namedtuple("TestCase", "config, day, sleeping, timeout_on, timeout_pre_off, timeout_leaving, timeout_pre_sleep, timeout_motion, timeout_door")

		light_config_max = LightConfigExtended(
			on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 2)),
			pre_off=FunctionConfig(day=BrightnessTimeout(40, 4), night=BrightnessTimeout(40, 1), sleeping=None),
			leaving=FunctionConfig(day=None, night=BrightnessTimeout(40, 15), sleeping=None),
			pre_sleep=FunctionConfig(day=None, night=BrightnessTimeout(10, 7), sleeping=None),
			motion=FunctionConfig(day=None, night=BrightnessTimeout(40, 20), sleeping=BrightnessTimeout(40, 9)),
			door=FunctionConfig(day=None, night=BrightnessTimeout(10, 21), sleeping=BrightnessTimeout(40, 8)),
			off_at_door_closed_during_leaving=True
		)

		light_config_min = LightConfigExtended(
			on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 2)),
			pre_off=None,
			leaving=None,
			pre_sleep=None,
			motion=None,
			door=None
		)

		test_cases = [
			TestCase(light_config_max, False, False, 5, 1, 15, 7, 20, 21),
			TestCase(light_config_max, False, True, 2, None, None, None, 9, 8),
			TestCase(light_config_max, True, False, 10, 4, None, None, None, None),
			TestCase(light_config_max, True, True, 2, None, None, None, 9, 8),

			TestCase(light_config_min, False, False, 5, None, None, None, None, None),
			TestCase(light_config_min, False, True, 2, None, None, None, None, None),
			TestCase(light_config_min, True, False, 10, None, None, None, None, None),
			TestCase(light_config_min, True, True, 2, None, None, None, None, None),
		]

		for test_case in test_cases:
			self.light_extended._item_day = HABApp.openhab.items.SwitchItem("day", "ON" if test_case.day else "OFF")
			self.light_extended._item_sleeping_state = HABApp.openhab.items.SwitchItem("sleeping", "sleeping" if test_case.sleeping else "awake")
			self.light_extended._config = test_case.config

			self.light_extended._set_timeouts()

			self.assertEqual(test_case.timeout_on, self.light_extended.state_machine.states["auto"].states["on"].timeout)
			self.assertEqual(test_case.timeout_pre_off, self.light_extended.state_machine.states["auto"].states["preoff"].timeout)
			self.assertEqual(test_case.timeout_leaving, self.light_extended.state_machine.states["auto"].states["leaving"].timeout)
			self.assertEqual(test_case.timeout_pre_sleep, self.light_extended.state_machine.states["auto"].states["presleep"].timeout)
			self.assertEqual(test_case.timeout_motion, self.light_extended.state_machine.states["auto"].states["motion"].timeout)
			self.assertEqual(test_case.timeout_door, self.light_extended.state_machine.states["auto"].states["door"].timeout)

	def test_get_target_brightness(self):
		"""Test _get_target_brightness."""
		light_config = LightConfigExtended(
			on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 5), sleeping=BrightnessTimeout(40, 2)),
			pre_off=FunctionConfig(day=BrightnessTimeout(40, 4), night=BrightnessTimeout(32, 1), sleeping=None),
			leaving=FunctionConfig(day=None, night=BrightnessTimeout(40, 15), sleeping=None),
			pre_sleep=FunctionConfig(day=None, night=BrightnessTimeout(10, 7), sleeping=None),
			motion=FunctionConfig(day=None, night=BrightnessTimeout(40, 20), sleeping=BrightnessTimeout(30, 9)),
			door=FunctionConfig(day=None, night=BrightnessTimeout(20, 21), sleeping=BrightnessTimeout(10, 8))
		)
		self.light_extended._config = light_config
		self.light_extended._brightness_before = 42
		self.light_extended._state_observer._value = 100
		self.light_extended._state_observer._last_manual_event = HABApp.openhab.events.ItemCommandEvent("Item_name", "ON")

		# tests for motion and door
		TestCase = collections.namedtuple("TestCase", "state, previous_state, day, sleeping, expected_value")
		test_cases = [
			# ============================== auto motion ==============================
			TestCase("auto_motion", previous_state="auto_off", day=False, sleeping=False, expected_value=40),
			TestCase("auto_motion", previous_state="auto_off", day=False, sleeping=True, expected_value=30),
			TestCase("auto_motion", previous_state="auto_off", day=True, sleeping=False, expected_value=None),
			TestCase("auto_motion", previous_state="auto_off", day=True, sleeping=True, expected_value=30),

			TestCase("auto_motion", previous_state="auto_door", day=False, sleeping=False, expected_value=40),
			TestCase("auto_motion", previous_state="auto_door", day=False, sleeping=True, expected_value=30),
			TestCase("auto_motion", previous_state="auto_door", day=True, sleeping=False, expected_value=None),
			TestCase("auto_motion", previous_state="auto_door", day=True, sleeping=True, expected_value=30),

			# ============================== auto door ==============================
			TestCase("auto_door", previous_state="auto_off", day=False, sleeping=False, expected_value=20),
			TestCase("auto_door", previous_state="auto_off", day=False, sleeping=True, expected_value=10),
			TestCase("auto_door", previous_state="auto_off", day=True, sleeping=False, expected_value=None),
			TestCase("auto_door", previous_state="auto_off", day=True, sleeping=True, expected_value=10),
		]

		# add test cases from normal light
		test_cases += TestLightBase.get_target_brightness_test_cases()

		# No motion and no door
		for test_case in test_cases:
			self.light_extended._item_sleeping_state.value = habapp_rules.system.SleepState.SLEEPING.value if test_case.sleeping else habapp_rules.system.SleepState.AWAKE.value
			self.light_extended._item_day.value = "ON" if test_case.day else "OFF"
			self.light_extended.state = test_case.state
			self.light_extended._previous_state = test_case.previous_state

			self.assertEqual(test_case.expected_value, self.light_extended._get_target_brightness(), test_case)

	def test_motion_configured(self):
		"""Test _moving_configured."""
		TestCase = collections.namedtuple("TestCase", "motion_item, timeout, result")
		item_motion = HABApp.openhab.items.SwitchItem.get_item("Unittest_Motion")

		test_cases = [
			TestCase(None, None, False),
			TestCase(None, 0, False),
			TestCase(None, 1, False),
			TestCase(None, 42, False),

			TestCase(item_motion, None, False),
			TestCase(item_motion, 0, False),
			TestCase(item_motion, 1, True),
			TestCase(item_motion, 42, True),
		]

		for test_case in test_cases:
			self.light_extended._item_motion = test_case.motion_item
			self.light_extended._timeout_motion = test_case.timeout
			self.assertEqual(test_case.result, self.light_extended._motion_configured())

	def test_door_configured(self):
		"""Test _door_configured."""
		TestCase = collections.namedtuple("TestCase", "door_items, timeout, result")
		door_items = [HABApp.openhab.items.ContactItem.get_item("Unittest_Door_1")]

		test_cases = [
			TestCase([], None, False),
			TestCase([], 0, False),
			TestCase([], 1, False),
			TestCase([], 42, False),

			TestCase(door_items, None, False),
			TestCase(door_items, 0, False),
			TestCase(door_items, 1, True),
			TestCase(door_items, 42, True),
		]

		for test_case in test_cases:
			self.light_extended._items_door = test_case.door_items
			self.light_extended._timeout_door = test_case.timeout
			self.assertEqual(test_case.result, self.light_extended._door_configured())

	def test_door_off_leaving_configured(self):
		"""Test _door_off_leaving_configured."""
		self.light_extended._config.off_at_door_closed_during_leaving = True
		self.assertTrue(self.light_extended._door_off_leaving_configured())

		self.light_extended._config.off_at_door_closed_during_leaving = False
		self.assertFalse(self.light_extended._door_off_leaving_configured())

	def test_motion_door_allowed(self):
		"""Test _motion_door_allowed"""
		with unittest.mock.patch("time.time", return_value=1000), unittest.mock.patch.object(self.light_extended, "_hand_off_timestamp", 100):
			self.assertTrue(self.light_extended._motion_door_allowed())

		with unittest.mock.patch("time.time", return_value=121), unittest.mock.patch.object(self.light_extended, "_hand_off_timestamp", 100):
			self.assertTrue(self.light_extended._motion_door_allowed())

		with unittest.mock.patch("time.time", return_value=120), unittest.mock.patch.object(self.light_extended, "_hand_off_timestamp", 100):
			self.assertFalse(self.light_extended._motion_door_allowed())

	def test_auto_motion(self):
		"""Test transitions of auto_motion."""
		# to auto_off by hand_off
		self.light_extended.to_auto_motion()
		self.light_extended._state_observer._value = 20
		tests.helper.oh_item.send_command("Unittest_Light", "OFF", "ON")
		self.assertEqual("auto_off", self.light_extended.state)

		# to auto_off by timeout (pre off NOT configured)
		self.light_extended.to_auto_motion()
		with unittest.mock.patch.object(self.light_extended, "_pre_off_configured", return_value=False):
			self.light_extended.motion_timeout()
		self.assertEqual("auto_off", self.light_extended.state)

		# to auto_preoff by timeout (pre off configured)
		self.light_extended.to_auto_motion()
		self.light_extended.motion_timeout()
		self.assertEqual("auto_preoff", self.light_extended.state)

		# to auto_off by motion off (pre off NOT configured)
		self.light_extended.to_auto_motion()
		with unittest.mock.patch.object(self.light_extended, "_pre_off_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Motion", "OFF", "ON")
		self.assertEqual("auto_off", self.light_extended.state)

		# to auto_preoff by motion off (pre off configured)
		self.light_extended.to_auto_motion()
		tests.helper.oh_item.send_command("Unittest_Motion", "OFF", "ON")
		self.assertEqual("auto_preoff", self.light_extended.state)

		# from auto_off to auto_motion (motion configured) | _motion_door_allowed = True
		with unittest.mock.patch.object(self.light_extended, "_motion_door_allowed", return_value=True):
			self.light_extended.to_auto_off()
			tests.helper.oh_item.send_command("Unittest_Motion", "ON", "OFF")
			self.assertEqual("auto_motion", self.light_extended.state)

		# from auto_off NOT to auto_motion (motion configured) | _motion_door_allowed = False
		with unittest.mock.patch.object(self.light_extended, "_motion_door_allowed", return_value=False):
			self.light_extended.to_auto_off()
			tests.helper.oh_item.send_command("Unittest_Motion", "ON", "OFF")
			self.assertEqual("auto_off", self.light_extended.state)

		# from auto_off to auto_motion (motion NOT configured)
		self.light_extended.to_auto_off()
		with unittest.mock.patch.object(self.light_extended, "_motion_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Motion", "ON", "OFF")
		self.assertEqual("auto_off", self.light_extended.state)

		# from auto_preoff to auto_motion (motion configured)
		self.light_extended.to_auto_preoff()
		tests.helper.oh_item.send_command("Unittest_Motion", "ON", "OFF")
		self.assertEqual("auto_motion", self.light_extended.state)

		# from auto_preoff to auto_motion (motion NOT configured)
		self.light_extended.to_auto_preoff()
		with unittest.mock.patch.object(self.light_extended, "_motion_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Motion", "ON", "OFF")
		self.assertEqual("auto_preoff", self.light_extended.state)

		# from auto_motion to auto_leaving (leaving configured)
		self.light_extended.to_auto_motion()
		tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_leaving", self.light_extended.state)

		# auto_motion no change at leaving (leaving NOT configured)
		self.light_extended.to_auto_motion()
		with unittest.mock.patch.object(self.light_extended, "_leaving_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_motion", self.light_extended.state)

		# from auto_motion to auto_presleep (pre sleep configured)
		self.light_extended.to_auto_motion()
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)
		self.assertEqual("auto_presleep", self.light_extended.state)

		# auto_motion no change at leaving (pre sleep NOT configured)
		self.light_extended.to_auto_motion()
		with unittest.mock.patch.object(self.light_extended, "_pre_sleep_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)
		self.assertEqual("auto_motion", self.light_extended.state)

	def test_auto_door(self):
		"""Test transitions of auto_door."""
		# to auto_off by hand_off
		self.light_extended.to_auto_door()
		self.light_extended._state_observer._value = 20
		tests.helper.oh_item.send_command("Unittest_Light", "OFF", "ON")
		self.assertEqual("auto_off", self.light_extended.state)

		# to auto_preoff by timeout (pre off configured)
		self.light_extended.to_auto_door()
		self.light_extended.door_timeout()
		self.assertEqual("auto_preoff", self.light_extended.state)

		# to auto_off by timeout (pre off NOT configured)
		self.light_extended.to_auto_door()
		with unittest.mock.patch.object(self.light_extended, "_pre_off_configured", return_value=False):
			self.light_extended.door_timeout()
		self.assertEqual("auto_off", self.light_extended.state)

		# to auto_motion by motion (motion configured)
		self.light_extended.to_auto_door()
		tests.helper.oh_item.send_command("Unittest_Motion", "ON", "OFF")
		self.assertEqual("auto_motion", self.light_extended.state)

		# no change by motion (motion NOT configured)
		self.light_extended.to_auto_door()
		with unittest.mock.patch.object(self.light_extended, "_motion_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Motion", "ON", "OFF")
		self.assertEqual("auto_door", self.light_extended.state)

		# auto_off to auto_door by first door (door configured) | _motion_door_allowed = True
		with unittest.mock.patch.object(self.light_extended, "_motion_door_allowed", return_value=True):
			self.light_extended.to_auto_off()
			tests.helper.oh_item.send_command("Unittest_Door_1", "OPEN", "CLOSED")
			self.assertEqual("auto_door", self.light_extended.state)

		# auto_off NOT to auto_door by first door (door configured) | _motion_door_allowed = False
		with unittest.mock.patch.object(self.light_extended, "_motion_door_allowed", return_value=False):
			self.light_extended.to_auto_off()
			tests.helper.oh_item.send_command("Unittest_Door_1", "OPEN", "CLOSED")
			self.assertEqual("auto_off", self.light_extended.state)

		# auto_off to auto_door by second door (door configured) | _motion_door_allowed = True
		with unittest.mock.patch.object(self.light_extended, "_motion_door_allowed", return_value=True):
			self.light_extended.to_auto_off()
			tests.helper.oh_item.send_command("Unittest_Door_2", "OPEN", "CLOSED")
			self.assertEqual("auto_door", self.light_extended.state)

		# auto_off NOT to auto_door by second door (door configured) | _motion_door_allowed = False
		with unittest.mock.patch.object(self.light_extended, "_motion_door_allowed", return_value=False):
			self.light_extended.to_auto_off()
			tests.helper.oh_item.send_command("Unittest_Door_2", "OPEN", "CLOSED")
			self.assertEqual("auto_off", self.light_extended.state)

		# auto_off NOT to auto_door first door (door NOT configured)
		self.light_extended.to_auto_off()
		with unittest.mock.patch.object(self.light_extended, "_door_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Door_1", "OPEN", "CLOSED")
		self.assertEqual("auto_off", self.light_extended.state)

		# from auto_door to auto_leaving (leaving configured)
		self.light_extended.to_auto_door()
		tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_leaving", self.light_extended.state)

		# auto_door no change at leaving (leaving NOT configured)
		self.light_extended.to_auto_door()
		with unittest.mock.patch.object(self.light_extended, "_leaving_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Presence_state", habapp_rules.system.PresenceState.LEAVING.value, habapp_rules.system.PresenceState.PRESENCE.value)
		self.assertEqual("auto_door", self.light_extended.state)

		# from auto_door to auto_presleep (pre sleep configured)
		self.light_extended.to_auto_door()
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)
		self.assertEqual("auto_presleep", self.light_extended.state)

		# auto_door no change at leaving (pre sleep NOT configured)
		self.light_extended.to_auto_door()
		with unittest.mock.patch.object(self.light_extended, "_pre_sleep_configured", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)
		self.assertEqual("auto_door", self.light_extended.state)

	def test_leaving(self):
		"""Test new extended transitions of auto_leaving."""
		# auto_leaving to auto_off by last door (door_off_leaving_configured configured)
		self.light_extended.to_auto_leaving()
		with unittest.mock.patch.object(self.light_extended._config, "off_at_door_closed_during_leaving", True):
			tests.helper.oh_item.send_command("Unittest_Door_1", "CLOSED", "OPEN")
		self.assertEqual("auto_off", self.light_extended.state)

		# auto_leaving no change by last door (off_at_door_closed_during_leaving NOT configured)
		self.light_extended.to_auto_leaving()
		with unittest.mock.patch.object(self.light_extended._config, "off_at_door_closed_during_leaving", False):
			tests.helper.oh_item.send_command("Unittest_Door_1", "CLOSED", "OPEN")
		self.assertEqual("auto_leaving", self.light_extended.state)

		# auto_leaving no change by door closed, but other door open (off_at_door_closed_during_leaving configured)
		self.light_extended.to_auto_leaving()
		tests.helper.oh_item.set_state("Unittest_Door_2", "OPEN")
		with unittest.mock.patch.object(self.light_extended._config, "off_at_door_closed_during_leaving", True):
			tests.helper.oh_item.send_command("Unittest_Door_1", "CLOSED", "OPEN")
		self.assertEqual("auto_leaving", self.light_extended.state)
