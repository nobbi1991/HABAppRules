"""Test sleep rule."""
import collections
import os
import pathlib
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import rules.common.state_machine_rule
import rules.system.sleep
import tests.common.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.timer


# pylint: disable=protected-access
class TestSleep(unittest.TestCase):
	"""Tests cases for testing presence rule."""

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

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep_Request", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Lock", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Lock_Request", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Display_Text", "")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_system_sleep_Sleep_state", "")

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()
		with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_system_sleep_Sleep_state", "")):
			self._sleep = rules.system.sleep.Sleep("Unittest_Sleep", "Unittest_Sleep_Request", "Unittest_Lock", "Unittest_Lock_Request", "Unittest_Display_Text")

	def test_create_graph(self):
		"""Create state machine graph for documentation."""
		presence_graph = tests.common.graph_machines.GraphMachineTimer(
			model=self._sleep,
			states=self._sleep.states,
			transitions=self._sleep.trans,
			initial=self._sleep.state,
			show_conditions=True
		)

		if os.name == "nt":
			presence_graph.get_graph().draw(pathlib.Path(__file__).parent / "Sleep.png", format="png", prog="dot")

	def test__init__(self):
		"""Test init of sleep class."""
		TestCase = collections.namedtuple("TestCase", "sleep_request_state, lock_request_state, lock_state")

		test_cases = [
			TestCase("OFF", "OFF", "OFF"),
			TestCase("OFF", "ON", "ON"),
			TestCase("ON", "OFF", "OFF"),
			TestCase("ON", "ON", "OFF"),
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Sleep_Request", test_case.sleep_request_state)
			tests.helper.oh_item.set_state("Unittest_Lock_Request", test_case.lock_request_state)

			with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_system_sleep_Sleep_state", "")):
				sleep = rules.system.sleep.Sleep("Unittest_Sleep", "Unittest_Sleep_Request", "Unittest_Lock", "Unittest_Lock_Request", "Unittest_Display_Text")

			self.assertEqual(sleep.sleep_request_active, test_case.sleep_request_state == "ON", test_case)
			self.assertEqual(sleep.lock_request_active, test_case.lock_request_state == "ON", test_case)
			tests.helper.oh_item.assert_value("Unittest_Sleep", test_case.sleep_request_state, test_case)
			tests.helper.oh_item.assert_value("Unittest_Lock", test_case.lock_state, test_case)

	def test_get_initial_state(self):
		"""Test getting initial state."""
		TestCase = collections.namedtuple("TestCase", "sleep_request, lock_request, expected_state")

		test_cases = [
			TestCase(sleep_request="OFF", lock_request="OFF", expected_state="awake"),
			TestCase(sleep_request="OFF", lock_request="ON", expected_state="locked"),
			TestCase(sleep_request="ON", lock_request="OFF", expected_state="sleeping"),
			TestCase(sleep_request="ON", lock_request="ON", expected_state="sleeping"),

			TestCase(sleep_request=None, lock_request="ON", expected_state="locked"),
			TestCase(sleep_request=None, lock_request="OFF", expected_state="default"),
			TestCase(sleep_request="ON", lock_request=None, expected_state="sleeping"),
			TestCase(sleep_request="OFF", lock_request=None, expected_state="awake"),

			TestCase(sleep_request=None, lock_request=None, expected_state="default")
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Sleep_Request", test_case.sleep_request)
			tests.helper.oh_item.set_state("Unittest_Lock_Request", test_case.lock_request)

			self.assertEqual(self._sleep._get_initial_state("default"), test_case.expected_state, test_case)

	def test__get_display_text(self):
		"""Test getting display text."""
		TestCase = collections.namedtuple("TestCase", "state, text")
		test_cases = [
			TestCase("awake", "Schlafen"),
			TestCase("pre_sleeping", "Guten Schlaf"),
			TestCase("sleeping", "Aufstehen"),
			TestCase("post_sleeping", "Guten Morgen"),
			TestCase("locked", "Gesperrt"),
			TestCase(None, "")
		]

		for test_case in test_cases:
			self._sleep.state = test_case.state
			self.assertEqual(test_case.text, self._sleep._Sleep__get_display_text())

	def test_normal_cycle_all_items(self):
		"""Test normal behavior with all items available."""
		# check initial state
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "awake")

		# start sleeping
		tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
		self.assertEqual(self._sleep.state, "pre_sleeping")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "pre_sleeping")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "ON")
		tests.helper.oh_item.assert_value("Unittest_Lock", "ON")
		tests.helper.oh_item.assert_value("Unittest_Display_Text", "Guten Schlaf")
		self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

		# pre_sleeping timeout -> sleep
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual(self._sleep.state, "sleeping")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "sleeping")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "ON")
		tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")
		tests.helper.oh_item.assert_value("Unittest_Display_Text", "Aufstehen")

		# stop sleeping
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.send_command("Unittest_Sleep_Request", "OFF", "ON")
		self.assertEqual(self._sleep.state, "post_sleeping")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "post_sleeping")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")
		tests.helper.oh_item.assert_value("Unittest_Lock", "ON")
		tests.helper.oh_item.assert_value("Unittest_Display_Text", "Guten Morgen")
		self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

		# post_sleeping timeout -> awake
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual(self._sleep.state, "awake")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "awake")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")
		tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")
		tests.helper.oh_item.assert_value("Unittest_Display_Text", "Schlafen")

	def test_lock_transitions(self):
		"""Test all transitions from and to locked state."""
		# check correct initial state
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "awake")
		tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")

		# set lock_request. expected: locked state, lock active, sleep off
		tests.helper.oh_item.send_command("Unittest_Lock_Request", "ON", "OFF")
		tests.helper.oh_item.assert_value("Unittest_Lock", "ON")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "locked")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

		# release lock and come back to awake state
		tests.helper.oh_item.send_command("Unittest_Lock_Request", "OFF", "ON")
		tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "awake")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

		# set lock_request and shortly after send sleep request -> locked expected
		tests.helper.oh_item.send_command("Unittest_Lock_Request", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
		tests.helper.oh_item.assert_value("Unittest_Sleep_Request", "OFF")
		tests.helper.oh_item.assert_value("Unittest_Lock", "ON")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "locked")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

		# release lock and jump back to awake
		tests.helper.oh_item.send_command("Unittest_Lock_Request", "OFF", "ON")
		tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "awake")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

		# start sleeping
		tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "pre_sleeping")

		# activate lock, remove sleep request and wait all timer -> expected state == locked
		tests.helper.oh_item.send_command("Unittest_Lock_Request", "ON", "OFF")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "pre_sleeping")
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "sleeping")
		tests.helper.oh_item.send_command("Unittest_Sleep_Request", "OFF", "ON")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "post_sleeping")
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "locked")

		# go back to pre_sleeping and check lock + end sleep in pre_sleeping -> expected state = locked
		tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "locked")
		tests.helper.oh_item.send_command("Unittest_Lock_Request", "OFF", "ON")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "awake")
		tests.helper.oh_item.send_command("Unittest_Lock_Request", "ON", "OFF")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "locked")

	def test_minimal_items(self):
		"""Test Sleeping class with minimal set of items."""
		# delete sleep rule from init
		self.__runner.loaded_rules[0]._unload()
		self.__runner.loaded_rules.clear()

		tests.helper.oh_item.remove_mocked_item_by_name("Unittest_Lock")
		tests.helper.oh_item.remove_mocked_item_by_name("Unittest_Lock_Request")
		tests.helper.oh_item.remove_mocked_item_by_name("Unittest_Display_Text")

		with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_system_sleep_Sleep_state", "")):
			self._sleep = rules.system.sleep.Sleep("Unittest_Sleep", "Unittest_Sleep_Request")

		self.assertIsNone(self._sleep._Sleep__item_display_text)
		self.assertIsNone(self._sleep._Sleep__item_lock)
		self.assertIsNone(self._sleep._Sleep__item_lock_request)

		# check initial state
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "awake")

		# start sleeping
		tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
		self.assertEqual(self._sleep.state, "pre_sleeping")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "pre_sleeping")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "ON")
		self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

		# pre_sleeping timeout -> sleep
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual(self._sleep.state, "sleeping")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "sleeping")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "ON")

		# stop sleeping
		self.transitions_timer_mock.reset_mock()
		tests.helper.oh_item.send_command("Unittest_Sleep_Request", "OFF", "ON")
		self.assertEqual(self._sleep.state, "post_sleeping")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "post_sleeping")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")
		self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

		# post_sleeping timeout -> awake
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual(self._sleep.state, "awake")
		tests.helper.oh_item.assert_value("rules_system_sleep_Sleep_state", "awake")
		tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()