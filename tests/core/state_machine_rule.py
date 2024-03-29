"""Unit-test for state_machine."""
import collections
import time
import unittest
import unittest.mock

import HABApp.openhab.items.switch_item

import habapp_rules.core.exceptions
import habapp_rules.core.state_machine_rule
import tests.helper.oh_item
import tests.helper.test_case_base


# pylint: disable=protected-access
class TestStateMachineRule(tests.helper.test_case_base.TestCaseBase):
	"""Tests for StateMachineRule."""

	def setUp(self) -> None:
		"""Setup unit-tests."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)
		self.item_exists_mock.return_value = False

		with unittest.mock.patch("habapp_rules.core.helper.create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_common_state_machine_rule_StateMachineRule_state", "")):
			self._state_machine = habapp_rules.core.state_machine_rule.StateMachineRule()

	def test__init(self):
		"""tests init of StateMachineRule."""
		with unittest.mock.patch("habapp_rules.core.helper.create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("some_name", "")) as create_mock:
			state_machine = habapp_rules.core.state_machine_rule.StateMachineRule()
			self.assertEqual("habapp_rules_core_state_machine_rule_TestRule_StateMachineRule", state_machine._item_prefix)
			create_mock.assert_called_once_with("H_habapp_rules_core_state_machine_rule_TestRule_StateMachineRule_state", "String", None)
			self.assertEqual("some_name", state_machine._item_state.name)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "state_name", "")
		self.item_exists_mock.return_value = True
		with unittest.mock.patch("habapp_rules.core.helper.create_additional_item") as create_mock:
			state_machine = habapp_rules.core.state_machine_rule.StateMachineRule("state_name")
			self.assertEqual("habapp_rules_core_state_machine_rule_TestRule_StateMachineRule", state_machine._item_prefix)
			create_mock.assert_not_called()
			self.assertEqual("state_name", state_machine._item_state.name)

	def test__init_exceptions(self):
		"""Test exceptions of __init__."""
		with unittest.mock.patch("habapp_rules.core.helper.create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_common_state_machine_rule_StateMachineRule_state", "")), \
				unittest.mock.patch("pathlib.Path.relative_to", side_effect=ValueError("not relative")):
			state_machine = habapp_rules.core.state_machine_rule.StateMachineRule()

		self.assertEqual("state_machine_rule_TestRule_StateMachineRule", state_machine._item_prefix)

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

	def test_on_rule_removed(self):
		"""Test on_rule_removed."""
		# check if 'on_rule_removed' is still available in HABApp
		getattr(HABApp.rule.Rule, "on_rule_removed")

		# check if timer is stopped correctly
		states = [
			{"name": "stopped"},
			{"name": "running", "timeout": 99, "on_timeout": "trigger_stop"}
		]

		with unittest.mock.patch("habapp_rules.core.helper.create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_common_state_machine_rule_StateMachineRule_state", "")):
			for initial_state in ["stopped", "running"]:
				state_machine_rule = habapp_rules.core.state_machine_rule.StateMachineRule()

				state_machine_rule.state_machine = habapp_rules.core.state_machine_rule.StateMachineWithTimeout(
					model=state_machine_rule,
					states=states,
					ignore_invalid_triggers=True)

				state_machine_rule._set_state(initial_state)

				if initial_state == "running":
					self.assertTrue(list(state_machine_rule.state_machine.states["running"].runner.values())[0].is_alive())

				state_machine_rule.on_rule_removed()

				if initial_state == "running":
					time.sleep(0.001)
					self.assertFalse(list(state_machine_rule.state_machine.states["running"].runner.values())[0].is_alive())
