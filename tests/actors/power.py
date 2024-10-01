"""Test power rules."""
import collections

import HABApp.rule.rule

import habapp_rules.actors.power
import habapp_rules.core.exceptions
import habapp_rules.core.state_machine_rule
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer
from habapp_rules.actors.config.power import CurrentSwitchConfig, CurrentSwitchItems, CurrentSwitchParameter


# pylint: disable=protected-access,no-member,too-many-public-methods
class TestCurrentSwitch(tests.helper.test_case_base.TestCaseBaseStateMachine):
	"""Tests cases for testing CurrentSwitch rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Current", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_1", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_2", None)

		self._rule_1 = habapp_rules.actors.power.CurrentSwitch(CurrentSwitchConfig(
			items=CurrentSwitchItems(
				current="Unittest_Current",
				switch="Unittest_Switch_1",
			)))

		self._rule_2 = habapp_rules.actors.power.CurrentSwitch(CurrentSwitchConfig(
			items=CurrentSwitchItems(
				current="Unittest_Current",
				switch="Unittest_Switch_2",
			),
			parameter=CurrentSwitchParameter(threshold=1000),
		))

	def test_init(self):
		"""Test __init__."""
		tests.helper.oh_item.assert_value("Unittest_Switch_1", None)
		tests.helper.oh_item.assert_value("Unittest_Switch_2", None)

	def test_current_changed(self):
		"""Test current changed."""
		TestCase = collections.namedtuple("TestCase", "current, expected_1, expected_2")

		test_cases = [
			TestCase(0, "OFF", "OFF"),
			TestCase(200, "OFF", "OFF"),
			TestCase(201, "ON", "OFF"),
			TestCase(1000, "ON", "OFF"),
			TestCase(1001, "ON", "ON"),
			TestCase(1001, "ON", "ON"),

			TestCase(1000, "ON", "OFF"),
			TestCase(200, "OFF", "OFF"),
			TestCase(0, "OFF", "OFF"),

			TestCase(-10000, "OFF", "OFF"),
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				tests.helper.oh_item.item_state_change_event("Unittest_Current", test_case.current)

				tests.helper.oh_item.assert_value("Unittest_Switch_1", test_case.expected_1)
				tests.helper.oh_item.assert_value("Unittest_Switch_2", test_case.expected_2)
