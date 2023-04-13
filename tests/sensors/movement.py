"""Tests for movement."""
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
import habapp_rules.sensors.movement
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

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Movement_min_raw", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Movement_min_filtered", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Movement_max_raw", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Movement_max_filtered", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Movement_max_lock", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness", 100)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness_Threshold", 1000)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Movement_Unittest_Movement_min_raw_state", "")

		with unittest.mock.patch.object(habapp_rules.core.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("H_Movement_Unittest_Movement_min_raw_state", "")):
			self.movement_min = habapp_rules.sensors.movement.Movement("Unittest_Movement_min_raw", "Unittest_Movement_min_filtered")
			self.movement_max = habapp_rules.sensors.movement.Movement("Unittest_Movement_max_raw", "Unittest_Movement_max_filtered", 5, "Unittest_Brightness", "Unittest_Brightness_Threshold", "Unittest_Movement_max_lock", "Unittest_Sleep_state")

	def test__init__(self):
		"""Test __init__."""
		expected_states = [
			{"name": "Locked"},
			{"name": "SleepLocked"},
			{"name": "PostSleepLocked", "timeout": 10, "on_timeout": "timeout_post_sleep_locked"},
			{"name": "Unlocked", "initial": "Init", "children": [
				{"name": "Init"},
				{"name": "Wait"},
				{"name": "Movement"},
				{"name": "MovementExtended", "timeout": 5, "on_timeout": "timeout_movement_extended"},
				{"name": "TooBright"}]}]
		self.assertEqual(expected_states, self.movement_min.states)

		expected_trans = [
			{"trigger": "lock_on", "source": ["Unlocked", "SleepLocked", "PostSleepLocked"], "dest": "Locked"},
			{"trigger": "lock_off", "source": "Locked", "dest": "Unlocked", "unless": "_sleep_active"},
			{"trigger": "lock_off", "source": "Locked", "dest": "SleepLocked", "conditions": "_sleep_active"},
			{"trigger": "sleep_started", "source": "Unlocked", "dest": "SleepLocked"},
			{"trigger": "sleep_end", "source": "SleepLocked", "dest": "Unlocked", "unless": "_post_sleep_lock_active"},
			{"trigger": "sleep_end", "source": "SleepLocked", "dest": "PostSleepLocked", "conditions": "_post_sleep_lock_active"},
			{"trigger": "timeout_post_sleep_locked", "source": "PostSleepLocked", "dest": "Unlocked", "unless": "_raw_movement_active"},
			{"trigger": "movement_off", "source": "PostSleepLocked", "dest": "PostSleepLocked"},
			{"trigger": "movement_on", "source": "PostSleepLocked", "dest": "PostSleepLocked"},
			{"trigger": "movement_on", "source": "Unlocked_Wait", "dest": "Unlocked_Movement"},
			{"trigger": "movement_off", "source": "Unlocked_Movement", "dest": "Unlocked_MovementExtended", "conditions": "_movement_extended_active"},
			{"trigger": "movement_off", "source": "Unlocked_Movement", "dest": "Unlocked_Wait", "unless": "_movement_extended_active"},
			{"trigger": "timeout_movement_extended", "source": "Unlocked_MovementExtended", "dest": "Unlocked_Wait"},
			{"trigger": "movement_on", "source": "Unlocked_MovementExtended", "dest": "Unlocked_Movement"},
			{"trigger": "brightness_over_threshold", "source": "Unlocked_Wait", "dest": "Unlocked_TooBright"},
			{"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Wait", "unless": "_raw_movement_active"},
			{"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Movement", "conditions": "_raw_movement_active"}
		]
		self.assertEqual(expected_trans, self.movement_min.trans)

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):  # pragma: no cover
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "Movement_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)

		light_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
			model=tests.helper.graph_machines.FakeModel(),
			states=self.movement_min.states,
			transitions=self.movement_min.trans,
			initial=self.movement_min.state,
			show_conditions=True)

		light_graph.get_graph().draw(picture_dir / "Movement.png", format="png", prog="dot")

	def test_init_exceptions(self):
		"""Test exceptions of __init__."""
		# brightness missing
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.sensors.movement.Movement("Unittest_Movement_max_raw", "Unittest_Movement_max_filtered", brightness_threshold="Unittest_Brightness_Threshold", name_lock="Unittest_Movement_max_lock", name_sleep_state="Unittest_Sleep_state")

		# brightness threshold missing
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.sensors.movement.Movement("Unittest_Movement_max_raw", "Unittest_Movement_max_filtered", name_brightness="Unittest_Brightness", name_lock="Unittest_Movement_max_lock", name_sleep_state="Unittest_Sleep_state")

	def test_initial_state(self):
		"""Test _get_initial_state."""
		TestCase = collections.namedtuple("TestCase", "locked, sleep_state, brightness, movement_raw, expected_state_max, expected_state_min")

		test_cases = [
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, movement_raw=False, expected_state_max="Unlocked_Wait", expected_state_min="Unlocked_Wait"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, movement_raw=True, expected_state_max="Unlocked_Movement", expected_state_min="Unlocked_Movement"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, movement_raw=False, expected_state_max="Unlocked_TooBright", expected_state_min="Unlocked_Wait"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, movement_raw=True, expected_state_max="Unlocked_TooBright", expected_state_min="Unlocked_Movement"),

			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, movement_raw=False, expected_state_max="SleepLocked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, movement_raw=True, expected_state_max="SleepLocked", expected_state_min="Unlocked_Movement"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, movement_raw=False, expected_state_max="SleepLocked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, movement_raw=True, expected_state_max="SleepLocked", expected_state_min="Unlocked_Movement"),

			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, movement_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, movement_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Movement"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, movement_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, movement_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Movement"),

			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, movement_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, movement_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Movement"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, movement_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
			TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, movement_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Movement"),
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Movement_max_lock", "ON" if test_case.locked else "OFF")
			tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_state)
			tests.helper.oh_item.set_state("Unittest_Brightness", test_case.brightness)
			tests.helper.oh_item.set_state("Unittest_Movement_max_raw", "ON" if test_case.movement_raw else "OFF")
			tests.helper.oh_item.set_state("Unittest_Movement_min_raw", "ON" if test_case.movement_raw else "OFF")

			self.assertEqual(test_case.expected_state_max, self.movement_max._get_initial_state("test"))
			self.assertEqual(test_case.expected_state_min, self.movement_min._get_initial_state("test"))

	def test_raw_movement_active(self):
		"""test _raw_movement_active"""
		tests.helper.oh_item.set_state("Unittest_Movement_min_raw", "ON")
		self.assertTrue(self.movement_min._raw_movement_active())

		tests.helper.oh_item.set_state("Unittest_Movement_min_raw", "OFF")
		self.assertFalse(self.movement_min._raw_movement_active())

	def test_get_brightness_threshold(self):
		"""test _get_brightness_threshold"""
		# value of threshold item
		self.assertEqual(1000, self.movement_max._get_brightness_threshold())

		# value given as parameter
		self.movement_max._brightness_threshold_value = 800
		self.assertEqual(800, self.movement_max._get_brightness_threshold())

	def test_get_brightness_threshold_exceptions(self):
		"""test exceptions of _get_brightness_threshold"""
		self.movement_max._item_brightness_threshold = None
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesException):
			self.movement_max._get_brightness_threshold()

	def test_initial_unlock_state(self):
		"""test initial state of unlock state."""
		TestCase = collections.namedtuple("TestCase", "brightness_value, movement_raw, expected_state_min, expected_state_max")

		test_cases = [
			TestCase(100, False, expected_state_min="Unlocked_Wait", expected_state_max="Unlocked_Wait"),
			TestCase(100, True, expected_state_min="Unlocked_Movement", expected_state_max="Unlocked_Movement"),
			TestCase(2000, False, expected_state_min="Unlocked_Wait", expected_state_max="Unlocked_TooBright"),
			TestCase(2000, True, expected_state_min="Unlocked_Movement", expected_state_max="Unlocked_TooBright"),
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Brightness", test_case.brightness_value)
			tests.helper.oh_item.set_state("Unittest_Movement_min_raw", "ON" if test_case.movement_raw else "OFF")
			tests.helper.oh_item.set_state("Unittest_Movement_max_raw", "ON" if test_case.movement_raw else "OFF")

			self.movement_min.to_Unlocked()
			self.movement_max.to_Unlocked()

			self.assertEqual(test_case.expected_state_min, self.movement_min.state)
			self.assertEqual(test_case.expected_state_max, self.movement_max.state)

	def test_lock(self):
		"""Test if lock is activated from all states."""
		for state in self._get_state_names(self.movement_max.states):
			tests.helper.oh_item.set_state("Unittest_Movement_max_lock", "OFF")
			self.movement_max.state = state
			tests.helper.oh_item.send_command("Unittest_Movement_max_lock", "ON", "OFF")
			self.assertEqual("Locked", self.movement_max.state)

	def test_movement_extended_active(self):
		"""Test _movement_extended_active"""
		self.movement_max._timeout_extended_movement = -1
		self.assertFalse(self.movement_max._movement_extended_active())

		self.movement_max._timeout_extended_movement = 0
		self.assertFalse(self.movement_max._movement_extended_active())

		self.movement_max._timeout_extended_movement = 1
		self.assertTrue(self.movement_max._movement_extended_active())

	def test_post_sleep_lock_active(self):
		"""Test _post_sleep_lock_active"""
		self.movement_max._timeout_post_sleep_lock = -1
		self.assertFalse(self.movement_max._post_sleep_lock_active())

		self.movement_max._timeout_post_sleep_lock = 0
		self.assertFalse(self.movement_max._post_sleep_lock_active())

		self.movement_max._timeout_post_sleep_lock = 1
		self.assertTrue(self.movement_max._post_sleep_lock_active())

	def test_sleep_active(self):
		"""Test _sleep_active"""
		tests.helper.oh_item.set_state("Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		self.assertFalse(self.movement_max._sleep_active())

		tests.helper.oh_item.set_state("Unittest_Sleep_state", habapp_rules.system.SleepState.SLEEPING.value)
		self.assertTrue(self.movement_max._sleep_active())

	def test_transitions_locked(self):
		"""Test leaving transitions of locked state."""
		# to Unlocked
		self.movement_max.state = "Locked"
		with unittest.mock.patch.object(self.movement_max, "_sleep_active", return_value=False):
			tests.helper.oh_item.send_command("Unittest_Movement_max_lock", "OFF", "ON")
		self.assertEqual("Unlocked_Wait", self.movement_max.state)

		# to SleepLocked
		self.movement_max.state = "Locked"
		with unittest.mock.patch.object(self.movement_max, "_sleep_active", return_value=True):
			tests.helper.oh_item.send_command("Unittest_Movement_max_lock", "OFF", "ON")
		self.assertEqual("SleepLocked", self.movement_max.state)

	def test_transitions_sleep_locked(self):
		"""Test leaving transitions of sleep locked state."""
		# to Unlocked
		self.movement_max.state = "SleepLocked"
		with unittest.mock.patch.object(self.movement_max, "_post_sleep_lock_active", return_value=False):
			self.movement_max.sleep_end()
		self.assertEqual("Unlocked_Wait", self.movement_max.state)

		# to PostSleepLocked
		self.movement_max.state = "SleepLocked"
		with unittest.mock.patch.object(self.movement_max, "_post_sleep_lock_active", return_value=True):
			self.movement_max.sleep_end()
		self.assertEqual("PostSleepLocked", self.movement_max.state)

	def test_transitions_post_sleep_locked(self):
		"""Test leaving transitions of post sleep locked state."""
		# to Unlocked | movement not active
		self.movement_max.state = "PostSleepLocked"
		with unittest.mock.patch.object(self.movement_max, "_raw_movement_active", return_value=False):
			self.movement_max.timeout_post_sleep_locked()
			self.assertEqual("Unlocked_Wait", self.movement_max.state)

		# no change after timeout and movement
		self.movement_max.state = "PostSleepLocked"
		with unittest.mock.patch.object(self.movement_max, "_raw_movement_active", return_value=True):
			self.movement_max.timeout_post_sleep_locked()
			self.assertEqual("PostSleepLocked", self.movement_max.state)

		# reset timer if movement off
		self.movement_max.state = "PostSleepLocked"
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.item_state_change_event("Unittest_Movement_max_raw", "OFF", "ON")
		self.assertEqual("PostSleepLocked", self.movement_max.state)
		self.assertEqual(1, self.transitions_timer_mock.call_count)

		# reset timer if movement on
		self.movement_max.state = "PostSleepLocked"
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.item_state_change_event("Unittest_Movement_max_raw", "ON", "OFF")
		self.assertEqual("PostSleepLocked", self.movement_max.state)
		self.assertEqual(1, self.transitions_timer_mock.call_count)

	def test_unlocked_wait(self):
		"""Test leaving transitions of Unlocked_Wait state."""
		# to movement
		self.movement_max.state = "Unlocked_Wait"
		self.movement_max.movement_on()
		self.assertEqual("Unlocked_Movement", self.movement_max.state)

		# to TooBright
		self.movement_max.state = "Unlocked_Wait"
		self.movement_max.brightness_over_threshold()
		self.assertEqual("Unlocked_TooBright", self.movement_max.state)

	def test_unlocked_movement(self):
		"""Test leaving transitions of Unlocked_Movement state."""
		# movement off | extended active
		self.movement_max.state = "Unlocked_Movement"
		with unittest.mock.patch.object(self.movement_max, "_movement_extended_active", return_value=True):
			self.movement_max.movement_off()
		self.assertEqual("Unlocked_MovementExtended", self.movement_max.state)

		# movement off | extended not active
		self.movement_max.state = "Unlocked_Movement"
		with unittest.mock.patch.object(self.movement_max, "_movement_extended_active", return_value=False):
			self.movement_max.movement_off()
		self.assertEqual("Unlocked_Wait", self.movement_max.state)

	def test_unlocked_movement_extended(self):
		"""Test leaving transitions of Unlocked_MovementExtended state."""
		# timeout
		self.movement_max.state = "Unlocked_MovementExtended"
		self.movement_max.timeout_movement_extended()
		self.assertEqual("Unlocked_Wait", self.movement_max.state)

		# movement on
		self.movement_max.state = "Unlocked_MovementExtended"
		self.movement_max.movement_on()
		self.assertEqual("Unlocked_Movement", self.movement_max.state)

	def test_unlocked_too_bright(self):
		"""Test leaving transitions of Unlocked_TooBright state."""
		# movement not active
		self.movement_max.state = "Unlocked_TooBright"
		with unittest.mock.patch.object(self.movement_max, "_raw_movement_active", return_value=False):
			self.movement_max.brightness_below_threshold()
		self.assertEqual("Unlocked_Wait", self.movement_max.state)

		# movement active
		self.movement_max.state = "Unlocked_TooBright"
		with unittest.mock.patch.object(self.movement_max, "_raw_movement_active", return_value=True):
			self.movement_max.brightness_below_threshold()
		self.assertEqual("Unlocked_Movement", self.movement_max.state)

	def test_check_brightness(self):
		"""Test _check_brightness."""
		with unittest.mock.patch.object(self.movement_max._hysteresis_switch, "get_output", return_value=True), \
				unittest.mock.patch.object(self.movement_max, "brightness_over_threshold"), \
				unittest.mock.patch.object(self.movement_max, "brightness_below_threshold"):
			self.movement_max._check_brightness()
			self.movement_max.brightness_over_threshold.assert_called_once()
			self.movement_max.brightness_below_threshold.assert_not_called()

		with unittest.mock.patch.object(self.movement_max._hysteresis_switch, "get_output", return_value=False), \
				unittest.mock.patch.object(self.movement_max, "brightness_over_threshold"), \
				unittest.mock.patch.object(self.movement_max, "brightness_below_threshold"):
			self.movement_max._check_brightness()
			self.movement_max.brightness_over_threshold.assert_not_called()
			self.movement_max.brightness_below_threshold.assert_called_once()

	def test_cb_brightness_threshold_change(self):
		"""Test _cb_threshold_change."""
		with unittest.mock.patch.object(self.movement_max._hysteresis_switch, "set_threshold_on"), unittest.mock.patch.object(self.movement_max, "_check_brightness"):
			tests.helper.oh_item.item_state_change_event("Unittest_Brightness_Threshold", 42)
			self.movement_max._hysteresis_switch.set_threshold_on.assert_called_once_with(42)
			self.movement_max._check_brightness.assert_called_once()

	def test_cb_movement_raw(self):
		"""Test _cb_movement_raw"""
		with unittest.mock.patch.object(self.movement_max, "movement_on"), unittest.mock.patch.object(self.movement_max, "movement_off"):
			tests.helper.oh_item.item_state_change_event("Unittest_Movement_max_raw", "ON", "OFF")
			self.movement_max.movement_on.assert_called_once()
			self.movement_max.movement_off.assert_not_called()

		with unittest.mock.patch.object(self.movement_max, "movement_on"), unittest.mock.patch.object(self.movement_max, "movement_off"):
			tests.helper.oh_item.item_state_change_event("Unittest_Movement_max_raw", "OFF", "ON")
			self.movement_max.movement_on.assert_not_called()
			self.movement_max.movement_off.assert_called_once()

	def test_cb_brightness_change(self):
		"""Test _cb_threshold_change."""
		with unittest.mock.patch.object(self.movement_max, "_check_brightness"):
			tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 42)
			self.movement_max._check_brightness.assert_called_once()

	def test_cb_sleep(self):
		"""Test _cb_sleep"""
		for state in habapp_rules.system.SleepState:
			with unittest.mock.patch.object(self.movement_max, "sleep_started"), unittest.mock.patch.object(self.movement_max, "sleep_end"):
				tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", state.value)
				if state == habapp_rules.system.SleepState.SLEEPING:
					self.movement_max.sleep_started.assert_called_once()
					self.movement_max.sleep_end.assert_not_called()

				elif state == habapp_rules.system.SleepState.AWAKE:
					self.movement_max.sleep_started.assert_not_called()
					self.movement_max.sleep_end.assert_called_once()

				else:
					self.movement_max.sleep_started.assert_not_called()
					self.movement_max.sleep_end.assert_not_called()

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
