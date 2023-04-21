"""Tests for motion."""
import collections
import os
import pathlib
import sys
import threading
import unittest
import unittest.mock

import HABApp

import habapp_rules.core.exceptions
import habapp_rules.core.state_machine_rule
import habapp_rules.sensors.motion
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner


# pylint: disable=no-member, protected-access, too-many-public-methods
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

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_min_raw", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_min_filtered", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_max_raw", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_max_filtered", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_max_lock", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness", 100)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness_Threshold", 1000)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Motion_Unittest_Motion_min_raw_state", "")

		with unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("H_Motion_Unittest_Motion_min_raw_state", "")):
			self.motion_min = habapp_rules.sensors.motion.Motion("Unittest_Motion_min_raw", "Unittest_Motion_min_filtered")
			self.motion_max = habapp_rules.sensors.motion.Motion("Unittest_Motion_max_raw", "Unittest_Motion_max_filtered", 5, "Unittest_Brightness", "Unittest_Brightness_Threshold", "Unittest_Motion_max_lock", "Unittest_Sleep_state")

	def test__init__(self):
		"""Test __init__."""
		expected_states = [
			{"name": "Locked"},
			{"name": "SleepLocked"},
			{"name": "PostSleepLocked", "timeout": 10, "on_timeout": "timeout_post_sleep_locked"},
			{"name": "Unlocked", "initial": "Init", "children": [
				{"name": "Init"},
				{"name": "Wait"},
				{"name": "Motion"},
				{"name": "MotionExtended", "timeout": 5, "on_timeout": "timeout_motion_extended"},
				{"name": "TooBright"}]}]
		self.assertEqual(expected_states, self.motion_min.states)

		expected_trans = [
			{"trigger": "lock_on", "source": ["Unlocked", "SleepLocked", "PostSleepLocked"], "dest": "Locked"},
			{"trigger": "lock_off", "source": "Locked", "dest": "Unlocked", "unless": "_sleep_active"},
			{"trigger": "lock_off", "source": "Locked", "dest": "SleepLocked", "conditions": "_sleep_active"},
			{"trigger": "sleep_started", "source": "Unlocked", "dest": "SleepLocked"},
			{"trigger": "sleep_end", "source": "SleepLocked", "dest": "Unlocked", "unless": "_post_sleep_lock_active"},
			{"trigger": "sleep_end", "source": "SleepLocked", "dest": "PostSleepLocked", "conditions": "_post_sleep_lock_active"},
			{"trigger": "timeout_post_sleep_locked", "source": "PostSleepLocked", "dest": "Unlocked", "unless": "_raw_motion_active"},
			{"trigger": "motion_off", "source": "PostSleepLocked", "dest": "PostSleepLocked"},
			{"trigger": "motion_on", "source": "PostSleepLocked", "dest": "PostSleepLocked"},
			{"trigger": "motion_on", "source": "Unlocked_Wait", "dest": "Unlocked_Motion"},
			{"trigger": "motion_off", "source": "Unlocked_Motion", "dest": "Unlocked_MotionExtended", "conditions": "_motion_extended_active"},
			{"trigger": "motion_off", "source": "Unlocked_Motion", "dest": "Unlocked_Wait", "unless": "_motion_extended_active"},
			{"trigger": "timeout_motion_extended", "source": "Unlocked_MotionExtended", "dest": "Unlocked_Wait"},
			{"trigger": "motion_on", "source": "Unlocked_MotionExtended", "dest": "Unlocked_Motion"},
			{"trigger": "brightness_over_threshold", "source": "Unlocked_Wait", "dest": "Unlocked_TooBright"},
			{"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Wait", "unless": "_raw_motion_active"},
			{"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Motion", "conditions": "_raw_motion_active"}
		]
		self.assertEqual(expected_trans, self.motion_min.trans)

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):  # pragma: no cover
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "Motion_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)

		light_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
			model=tests.helper.graph_machines.FakeModel(),
			states=self.motion_min.states,
			transitions=self.motion_min.trans,
			initial=self.motion_min.state,
			show_conditions=True)

		light_graph.get_graph().draw(picture_dir / "Motion.png", format="png", prog="dot")

	def test_init_exceptions(self):
		"""Test exceptions of __init__."""
		# brightness missing
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.sensors.motion.Motion("Unittest_Motion_max_raw", "Unittest_Motion_max_filtered", brightness_threshold="Unittest_Brightness_Threshold", name_lock="Unittest_Motion_max_lock", name_sleep_state="Unittest_Sleep_state")

		# brightness threshold missing
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.sensors.motion.Motion("Unittest_Motion_max_raw", "Unittest_Motion_max_filtered", name_brightness="Unittest_Brightness", name_lock="Unittest_Motion_max_lock", name_sleep_state="Unittest_Sleep_state")

	def test_initial_state(self):
		"""Test _get_initial_state."""
		TestCase = collections.namedtuple("TestCase", "locked, sleep_state, brightness, motion_raw, expected_state_max, expected_state_min")

		test_cases = [
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, motion_raw=False, expected_state_max="Unlocked_Wait", expected_state_min="Unlocked_Wait"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, motion_raw=True, expected_state_max="Unlocked_Motion", expected_state_min="Unlocked_Motion"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, motion_raw=False, expected_state_max="Unlocked_TooBright", expected_state_min="Unlocked_Wait"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, motion_raw=True, expected_state_max="Unlocked_TooBright", expected_state_min="Unlocked_Motion"),

			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, motion_raw=False, expected_state_max="SleepLocked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, motion_raw=True, expected_state_max="SleepLocked", expected_state_min="Unlocked_Motion"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, motion_raw=False, expected_state_max="SleepLocked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, motion_raw=True, expected_state_max="SleepLocked", expected_state_min="Unlocked_Motion"),

			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, motion_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, motion_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Motion"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, motion_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, motion_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Motion"),

			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, motion_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, motion_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Motion"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, motion_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, motion_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Motion"),
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Motion_max_lock", "ON" if test_case.locked else "OFF")
			tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_state)
			tests.helper.oh_item.set_state("Unittest_Brightness", test_case.brightness)
			tests.helper.oh_item.set_state("Unittest_Motion_max_raw", "ON" if test_case.motion_raw else "OFF")
			tests.helper.oh_item.set_state("Unittest_Motion_min_raw", "ON" if test_case.motion_raw else "OFF")

			self.assertEqual(test_case.expected_state_max, self.motion_max._get_initial_state("test"))
			self.assertEqual(test_case.expected_state_min, self.motion_min._get_initial_state("test"))

	def test_raw_motion_active(self):
		"""test _raw_motion_active"""
		tests.helper.oh_item.set_state("Unittest_Motion_min_raw", "ON")
		self.assertTrue(self.motion_min._raw_motion_active())

		tests.helper.oh_item.set_state("Unittest_Motion_min_raw", "OFF")
		self.assertFalse(self.motion_min._raw_motion_active())

	def test_get_brightness_threshold(self):
		"""test _get_brightness_threshold"""
		# value of threshold item
		self.assertEqual(1000, self.motion_max._get_brightness_threshold())

		# value given as parameter
		self.motion_max._brightness_threshold_value = 800
		self.assertEqual(800, self.motion_max._get_brightness_threshold())

	def test_get_brightness_threshold_exceptions(self):
		"""test exceptions of _get_brightness_threshold"""
		self.motion_max._item_brightness_threshold = None
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesException):
			self.motion_max._get_brightness_threshold()

	def test_initial_unlock_state(self):
		"""test initial state of unlock state."""
		TestCase = collections.namedtuple("TestCase", "brightness_value, motion_raw, expected_state_min, expected_state_max")

		test_cases = [
			TestCase(100, False, expected_state_min="Unlocked_Wait", expected_state_max="Unlocked_Wait"),
			TestCase(100, True, expected_state_min="Unlocked_Motion", expected_state_max="Unlocked_Motion"),
			TestCase(2000, False, expected_state_min="Unlocked_Wait", expected_state_max="Unlocked_TooBright"),
			TestCase(2000, True, expected_state_min="Unlocked_Motion", expected_state_max="Unlocked_TooBright"),
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Brightness", test_case.brightness_value)
			tests.helper.oh_item.set_state("Unittest_Motion_min_raw", "ON" if test_case.motion_raw else "OFF")
			tests.helper.oh_item.set_state("Unittest_Motion_max_raw", "ON" if test_case.motion_raw else "OFF")

			self.motion_min.to_Unlocked()
			self.motion_max.to_Unlocked()

			self.assertEqual(test_case.expected_state_min, self.motion_min.state)
			self.assertEqual(test_case.expected_state_max, self.motion_max.state)

	def test_lock(self):
		"""Test if lock is activated from all states."""
		for state in self._get_state_names(self.motion_max.states):
			tests.helper.oh_item.set_state("Unittest_Motion_max_lock", "OFF")
			self.motion_max.state = state
			tests.helper.oh_item.send_command("Unittest_Motion_max_lock", "ON", "OFF")
			self.assertEqual("Locked", self.motion_max.state)

	def test_motion_extended_active(self):
		"""Test _motion_extended_active"""
		self.motion_max._timeout_extended_motion = -1
		self.assertFalse(self.motion_max._motion_extended_active())

		self.motion_max._timeout_extended_motion = 0
		self.assertFalse(self.motion_max._motion_extended_active())

		self.motion_max._timeout_extended_motion = 1
		self.assertTrue(self.motion_max._motion_extended_active())

	def test_post_sleep_lock_active(self):
		"""Test _post_sleep_lock_active"""
		self.motion_max._timeout_post_sleep_lock = -1
		self.assertFalse(self.motion_max._post_sleep_lock_active())

		self.motion_max._timeout_post_sleep_lock = 0
		self.assertFalse(self.motion_max._post_sleep_lock_active())

		self.motion_max._timeout_post_sleep_lock = 1
		self.assertTrue(self.motion_max._post_sleep_lock_active())

	def test_sleep_active(self):
		"""Test _sleep_active"""
		tests.helper.oh_item.set_state("Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		self.assertFalse(self.motion_max._sleep_active())

		tests.helper.oh_item.set_state("Unittest_Sleep_state", habapp_rules.system.SleepState.SLEEPING.value)
		self.assertTrue(self.motion_max._sleep_active())

	def test_transitions_locked(self):
		"""Test leaving transitions of locked state."""
		# to Unlocked
		self.motion_max.state = "Locked"
		with unittest.mock.patch.object(self.motion_max, "_sleep_active", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Motion_max_lock", "OFF", "ON")
		self.assertEqual("Unlocked_Wait", self.motion_max.state)

		# to SleepLocked
		self.motion_max.state = "Locked"
		with unittest.mock.patch.object(self.motion_max, "_sleep_active", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Motion_max_lock", "OFF", "ON")
		self.assertEqual("SleepLocked", self.motion_max.state)

	def test_transitions_sleep_locked(self):
		"""Test leaving transitions of sleep locked state."""
		# to Unlocked
		self.motion_max.state = "SleepLocked"
		with unittest.mock.patch.object(self.motion_max, "_post_sleep_lock_active", return_value=False):
			self.motion_max.sleep_end()
		self.assertEqual("Unlocked_Wait", self.motion_max.state)

		# to PostSleepLocked
		self.motion_max.state = "SleepLocked"
		with unittest.mock.patch.object(self.motion_max, "_post_sleep_lock_active", return_value=True):
			self.motion_max.sleep_end()
		self.assertEqual("PostSleepLocked", self.motion_max.state)

	def test_transitions_post_sleep_locked(self):
		"""Test leaving transitions of post sleep locked state."""
		# to Unlocked | motion not active
		self.motion_max.state = "PostSleepLocked"
		with unittest.mock.patch.object(self.motion_max, "_raw_motion_active", return_value=False):
			self.motion_max.timeout_post_sleep_locked()
			self.assertEqual("Unlocked_Wait", self.motion_max.state)

		# no change after timeout and motion
		self.motion_max.state = "PostSleepLocked"
		with unittest.mock.patch.object(self.motion_max, "_raw_motion_active", return_value=True):
			self.motion_max.timeout_post_sleep_locked()
			self.assertEqual("PostSleepLocked", self.motion_max.state)

		# reset timer if motion off
		self.motion_max.state = "PostSleepLocked"
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.item_state_change_event("Unittest_Motion_max_raw", "OFF", "ON")
		self.assertEqual("PostSleepLocked", self.motion_max.state)
		self.assertEqual(1, self.transitions_timer_mock.call_count)

		# reset timer if motion on
		self.motion_max.state = "PostSleepLocked"
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.item_state_change_event("Unittest_Motion_max_raw", "ON", "OFF")
		self.assertEqual("PostSleepLocked", self.motion_max.state)
		self.assertEqual(1, self.transitions_timer_mock.call_count)

	def test_unlocked_wait(self):
		"""Test leaving transitions of Unlocked_Wait state."""
		# to motion
		self.motion_max.state = "Unlocked_Wait"
		self.motion_max.motion_on()
		self.assertEqual("Unlocked_Motion", self.motion_max.state)

		# to TooBright
		self.motion_max.state = "Unlocked_Wait"
		self.motion_max.brightness_over_threshold()
		self.assertEqual("Unlocked_TooBright", self.motion_max.state)

	def test_unlocked_motion(self):
		"""Test leaving transitions of Unlocked_Motion state."""
		# motion off | extended active
		self.motion_max.state = "Unlocked_Motion"
		with unittest.mock.patch.object(self.motion_max, "_motion_extended_active", return_value=True):
			self.motion_max.motion_off()
		self.assertEqual("Unlocked_MotionExtended", self.motion_max.state)

		# motion off | extended not active
		self.motion_max.state = "Unlocked_Motion"
		with unittest.mock.patch.object(self.motion_max, "_motion_extended_active", return_value=False):
			self.motion_max.motion_off()
		self.assertEqual("Unlocked_Wait", self.motion_max.state)

	def test_unlocked_motion_extended(self):
		"""Test leaving transitions of Unlocked_MotionExtended state."""
		# timeout
		self.motion_max.state = "Unlocked_MotionExtended"
		self.motion_max.timeout_motion_extended()
		self.assertEqual("Unlocked_Wait", self.motion_max.state)

		# motion on
		self.motion_max.state = "Unlocked_MotionExtended"
		self.motion_max.motion_on()
		self.assertEqual("Unlocked_Motion", self.motion_max.state)

	def test_unlocked_too_bright(self):
		"""Test leaving transitions of Unlocked_TooBright state."""
		# motion not active
		self.motion_max.state = "Unlocked_TooBright"
		with unittest.mock.patch.object(self.motion_max, "_raw_motion_active", return_value=False):
			self.motion_max.brightness_below_threshold()
		self.assertEqual("Unlocked_Wait", self.motion_max.state)

		# motion active
		self.motion_max.state = "Unlocked_TooBright"
		with unittest.mock.patch.object(self.motion_max, "_raw_motion_active", return_value=True):
			self.motion_max.brightness_below_threshold()
		self.assertEqual("Unlocked_Motion", self.motion_max.state)

	def test_check_brightness(self):
		"""Test _check_brightness."""
		with unittest.mock.patch.object(self.motion_max._hysteresis_switch, "get_output", return_value=True), \
				unittest.mock.patch.object(self.motion_max, "brightness_over_threshold"), \
				unittest.mock.patch.object(self.motion_max, "brightness_below_threshold"):
			self.motion_max._check_brightness()
			self.motion_max.brightness_over_threshold.assert_called_once()
			self.motion_max.brightness_below_threshold.assert_not_called()

		with unittest.mock.patch.object(self.motion_max._hysteresis_switch, "get_output", return_value=False), \
				unittest.mock.patch.object(self.motion_max, "brightness_over_threshold"), \
				unittest.mock.patch.object(self.motion_max, "brightness_below_threshold"):
			self.motion_max._check_brightness()
			self.motion_max.brightness_over_threshold.assert_not_called()
			self.motion_max.brightness_below_threshold.assert_called_once()

	def test_cb_brightness_threshold_change(self):
		"""Test _cb_threshold_change."""
		with unittest.mock.patch.object(self.motion_max._hysteresis_switch, "set_threshold_on"), unittest.mock.patch.object(self.motion_max, "_check_brightness"):
			tests.helper.oh_item.item_state_change_event("Unittest_Brightness_Threshold", 42)
			self.motion_max._hysteresis_switch.set_threshold_on.assert_called_once_with(42)
			self.motion_max._check_brightness.assert_called_once()

	def test_cb_motion_raw(self):
		"""Test _cb_motion_raw"""
		with unittest.mock.patch.object(self.motion_max, "motion_on"), unittest.mock.patch.object(self.motion_max, "motion_off"):
			tests.helper.oh_item.item_state_change_event("Unittest_Motion_max_raw", "ON", "OFF")
			self.motion_max.motion_on.assert_called_once()
			self.motion_max.motion_off.assert_not_called()

		with unittest.mock.patch.object(self.motion_max, "motion_on"), unittest.mock.patch.object(self.motion_max, "motion_off"):
			tests.helper.oh_item.item_state_change_event("Unittest_Motion_max_raw", "OFF", "ON")
			self.motion_max.motion_on.assert_not_called()
			self.motion_max.motion_off.assert_called_once()

	def test_cb_brightness_change(self):
		"""Test _cb_threshold_change."""
		with unittest.mock.patch.object(self.motion_max, "_check_brightness"):
			tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 42)
			self.motion_max._check_brightness.assert_called_once()

	def test_cb_sleep(self):
		"""Test _cb_sleep"""
		for state in habapp_rules.system.SleepState:
			with unittest.mock.patch.object(self.motion_max, "sleep_started"), unittest.mock.patch.object(self.motion_max, "sleep_end"):
				tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", state.value)
				if state == habapp_rules.system.SleepState.SLEEPING:
					self.motion_max.sleep_started.assert_called_once()
					self.motion_max.sleep_end.assert_not_called()

				elif state == habapp_rules.system.SleepState.AWAKE:
					self.motion_max.sleep_started.assert_not_called()
					self.motion_max.sleep_end.assert_called_once()

				else:
					self.motion_max.sleep_started.assert_not_called()
					self.motion_max.sleep_end.assert_not_called()

	def _get_state_names(self, states: dict, parent_state: str | None = None) -> list[str]:  # pragma: no cover
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
				state_names += self._get_state_names(state, state["name"])
			else:
				state_names.append(f"{prefix}{state['name']}")
		return state_names

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
