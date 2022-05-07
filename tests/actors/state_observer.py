"""Test Presence rule."""
import collections
import os
import pathlib
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import rules.common.state_machine_rule
import rules.system.presence
import tests.common.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.timer
import rules.actors.state_observer


# pylint: disable=protected-access
class TestPresence(unittest.TestCase):
	"""Tests cases for testing presence rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.send_command_mock_patcher.stop)
		self.send_command_mock = self.send_command_mock_patcher.start()

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_ctr", 0)
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Leaving", "OFF")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone1", "ON")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone2", "OFF")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_system_presence_Presence_state", "")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Presence", "ON")

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()

		self._cb_dimmer = unittest.mock.MagicMock()
		self._observer_dimmer = rules.actors.state_observer.StateObserver("Unittest_Dimmer", self._cb_dimmer, control_names=["Unittest_Dimmer_ctr"])

	def test_dimmer_from_habapp(self):
		"""Test dimmer when sending from HABApp rule."""
		self._observer_dimmer.send_command(0)
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", 0)
		self._cb_dimmer.assert_not_called()
		self._observer_dimmer.send_command(30)
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", 30)
		self._cb_dimmer.assert_not_called()
		self._observer_dimmer.send_command(100)
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", 100)
		self._cb_dimmer.assert_not_called()

	def test_dimmer_manu_from_ctr(self):
		"""Test manual detection from control item."""
		TestCase = collections.namedtuple("TestCase", "command, state, wait_for_value")

		test_cases = [
			TestCase(100, 100, True),
			TestCase(100, 100, False),
			TestCase(0, 0, True),
			TestCase("ON", 100, True),
			TestCase("OFF", 0, True),
			TestCase("INCREASE", 30, True)
		]

		for idx, test_case in enumerate(test_cases):
			tests.helper.oh_item.item_command_event("Unittest_Dimmer_ctr", test_case.command)
			if test_case.wait_for_value:
				self.assertTrue(self._observer_dimmer.wait_for_value)
			self.assertEqual(idx + 1, self._cb_dimmer.call_count)
			self._cb_dimmer.assert_called_with(unittest.mock.ANY, "Manual from KNX-Bus")
			tests.helper.oh_item.item_state_event("Unittest_Dimmer", test_case.state)
			self.assertEqual(test_case.state, self._observer_dimmer.value)
			self.assertFalse(self._observer_dimmer.wait_for_value)

	def test_dimmer_manu_from_openhab(self):
		"""Test manual detection from control item."""
		TestCase = collections.namedtuple("TestCase", "command, state, wait_for_value")

		test_cases = [
			TestCase(100, 100, True),
			TestCase(100, 100, False),
			TestCase(0, 0, True),
			TestCase("ON", 100, True),
			TestCase("OFF", 0, True),
			TestCase("INCREASE", 30, True)
		]

		for idx, test_case in enumerate(test_cases):
			tests.helper.oh_item.item_command_event("Unittest_Dimmer", test_case.command)
			if test_case.wait_for_value:
				self.assertTrue(self._observer_dimmer.wait_for_value)
			self.assertEqual(idx + 1, self._cb_dimmer.call_count)
			self._cb_dimmer.assert_called_with(unittest.mock.ANY, "Manual from OpenHAB")
			tests.helper.oh_item.item_state_event("Unittest_Dimmer", test_case.state)
			self.assertEqual(test_case.state, self._observer_dimmer.value)
			self.assertFalse(self._observer_dimmer.wait_for_value)

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
