"""Unit-test for state_machine."""
import collections
import unittest
import unittest.mock

import HABApp.openhab.items.switch_item

import rules.common.state_machine_rule
import tests.helper.rule_runner


# pylint: disable=protected-access
class TestStateMachineRule(unittest.TestCase):
	"""Tests for StateMachineRule."""

	def setUp(self) -> None:
		"""Setup unit-tests."""
		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()

		with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_common_state_machine_rule_StateMachineRule_state", "")):
			self._state_machine = rules.common.state_machine_rule.StateMachineRule()

	def test__init(self):
		"""tests init of StateMachineRule."""
		with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item") as create_mock:
			state_machine = rules.common.state_machine_rule.StateMachineRule()
			self.assertEqual("rules_common_state_machine_rule_StateMachineRule", state_machine._item_prefix)
			create_mock.assert_called_once_with("rules_common_state_machine_rule_StateMachineRule_state", "String")

	def test_create_additional_item(self):
		"""Test create additional item."""
		# check if item is created if NOT existing
		with unittest.mock.patch("HABApp.openhab.interface.item_exists", spec=HABApp.openhab.interface.item_exists, return_value=False), \
				unittest.mock.patch("HABApp.openhab.interface.create_item", spec=HABApp.openhab.interface.create_item) as create_mock, \
				unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
			self._state_machine._create_additional_item("Name_of_Item", "Switch")
			create_mock.assert_called_once_with(item_type="Switch", name="Name_of_Item", label="Name of Item")

		# check if item is NOT created if existing
		with unittest.mock.patch("HABApp.openhab.interface.item_exists", spec=HABApp.openhab.interface.item_exists, return_value=True), \
				unittest.mock.patch("HABApp.openhab.interface.create_item", spec=HABApp.openhab.interface.create_item) as create_mock, \
				unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
			self._state_machine._create_additional_item("Name_of_Item", "Switch")
			create_mock.assert_not_called()

	def test_get_initial_state(self):
		"""Test getting of initial state."""
		TestCase = collections.namedtuple("TestCase", "item_value, state_names, default, expected_result")
		test_cases = [
			TestCase("state1", ["state1", "state2"], "default", "state1"),
			TestCase("wrong_state", ["state1", "state2"], "default", "default"),
			TestCase("state1", ["new_state1", "new_state_2"], "default", "default"),
			TestCase("state1", [], "default", "default")
		]

		with unittest.mock.patch.object(self._state_machine, "_item_state") as state_item_mock:
			for test_case in test_cases:
				state_item_mock.value = test_case.item_value
				self._state_machine.states = [{"name": name} for name in test_case.state_names]
				self.assertEqual(self._state_machine._get_initial_state(test_case.default), test_case.expected_result)

	def test_update_openhab_state(self):
		"""Test if OpenHAB state will be updated."""
		self._state_machine.state = "some_state"
		with unittest.mock.patch.object(self._state_machine, "_item_state") as state_item:
			self._state_machine._update_openhab_state()
			state_item.oh_send_command.assert_called_once_with("some_state")

	def tearDown(self) -> None:
		"""Tear down unit-test."""
		self.__runner.tear_down()
