"""Test power rules."""

import collections
import unittest.mock

import HABApp.rule.rule
import HABApp.rule.scheduler.job_ctrl

import habapp_rules.sensors.current_switch
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.sensors.config.current_switch import CurrentSwitchConfig, CurrentSwitchItems, CurrentSwitchParameter


class TestCurrentSwitch(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing CurrentSwitch rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Current", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_extended", None)

        self._rule_1 = habapp_rules.sensors.current_switch.CurrentSwitch(
            CurrentSwitchConfig(
                items=CurrentSwitchItems(
                    current="Unittest_Current",
                    switch="Unittest_Switch_1",
                )
            )
        )

        self._rule_2 = habapp_rules.sensors.current_switch.CurrentSwitch(
            CurrentSwitchConfig(
                items=CurrentSwitchItems(
                    current="Unittest_Current",
                    switch="Unittest_Switch_2",
                ),
                parameter=CurrentSwitchParameter(threshold=1),
            )
        )

        self._rule_extended = habapp_rules.sensors.current_switch.CurrentSwitch(
            CurrentSwitchConfig(
                items=CurrentSwitchItems(
                    current="Unittest_Current",
                    switch="Unittest_Switch_extended",
                ),
                parameter=CurrentSwitchParameter(extended_time=60),
            )
        )

    def test_init(self) -> None:
        """Test __init__."""
        tests.helper.oh_item.assert_value("Unittest_Switch_1", None)
        tests.helper.oh_item.assert_value("Unittest_Switch_2", None)
        tests.helper.oh_item.assert_value("Unittest_Switch_extended", None)

        self.assertIsNone(self._rule_1._extended_countdown)
        self.assertIsNone(self._rule_2._extended_countdown)
        self.assertIsInstance(self._rule_extended._extended_countdown, HABApp.rule.scheduler.job_ctrl.CountdownJobControl)
        self.assertIsNone(self._rule_extended._extended_countdown.next_run_datetime)

    def test_current_changed_without_extended_time(self) -> None:
        """Test current changed without extended time."""
        TestCase = collections.namedtuple("TestCase", "current, expected_1, expected_2")

        test_cases = [
            TestCase(0, "OFF", "OFF"),
            TestCase(0.2, "OFF", "OFF"),
            TestCase(0.201, "ON", "OFF"),
            TestCase(1, "ON", "OFF"),
            TestCase(1.001, "ON", "ON"),
            TestCase(1.001, "ON", "ON"),
            TestCase(1, "ON", "OFF"),
            TestCase(0.200, "OFF", "OFF"),
            TestCase(0, "OFF", "OFF"),
            TestCase(-10000, "OFF", "OFF"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.item_state_change_event("Unittest_Current", test_case.current)

                tests.helper.oh_item.assert_value("Unittest_Switch_1", test_case.expected_1)
                tests.helper.oh_item.assert_value("Unittest_Switch_2", test_case.expected_2)

    def test_current_changed_with_extended_time(self) -> None:
        """Test current changed with extended time."""
        with unittest.mock.patch.object(self._rule_extended, "_extended_countdown") as countdown_mock:
            # below threshold
            tests.helper.oh_item.item_state_change_event("Unittest_Current", 0.1)
            tests.helper.oh_item.assert_value("Unittest_Switch_extended", None)
            countdown_mock.stop.assert_not_called()
            countdown_mock.reset.assert_not_called()

            # above threshold
            tests.helper.oh_item.item_state_change_event("Unittest_Current", 0.3)
            tests.helper.oh_item.assert_value("Unittest_Switch_extended", "ON")
            countdown_mock.stop.assert_called_once()
            countdown_mock.reset.assert_not_called()

            # below threshold
            countdown_mock.stop.reset_mock()
            tests.helper.oh_item.item_state_change_event("Unittest_Current", 0.1)
            tests.helper.oh_item.assert_value("Unittest_Switch_extended", "ON")
            countdown_mock.stop.assert_not_called()
            countdown_mock.reset.assert_called_once()
