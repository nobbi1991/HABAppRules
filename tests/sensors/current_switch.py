"""Test power rules."""

import collections
import unittest.mock

from HABApp.openhab.items import NumberItem, SwitchItem
from HABApp.rule.scheduler.job_ctrl import CountdownJobControl

from habapp_rules.sensors.config.current_switch import CurrentSwitchConfig, CurrentSwitchItems, CurrentSwitchParameter
from habapp_rules.sensors.current_switch import CurrentSwitch
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_change_event,
)
from tests.helper.test_case_base import TestCaseBaseStateMachine


class TestCurrentSwitch(TestCaseBaseStateMachine):
    """Tests cases for testing CurrentSwitch rule."""

    def setUp(self) -> None:
        """Setup test case."""
        super().setUp()

        add_mock_item(NumberItem, "Unittest_Current", None)
        add_mock_item(SwitchItem, "Unittest_Switch_1", None)
        add_mock_item(SwitchItem, "Unittest_Switch_2", None)
        add_mock_item(SwitchItem, "Unittest_Switch_extended", None)

        self._rule_1 = CurrentSwitch(
            CurrentSwitchConfig(
                items=CurrentSwitchItems(
                    current="Unittest_Current",
                    switch="Unittest_Switch_1",
                )
            )
        )

        self._rule_2 = CurrentSwitch(
            CurrentSwitchConfig(
                items=CurrentSwitchItems(
                    current="Unittest_Current",
                    switch="Unittest_Switch_2",
                ),
                parameter=CurrentSwitchParameter(threshold=1),
            )
        )

        self._rule_extended = CurrentSwitch(
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
        assert_item_value("Unittest_Switch_1", None)
        assert_item_value("Unittest_Switch_2", None)
        assert_item_value("Unittest_Switch_extended", None)

        self.assertIsNone(self._rule_1._extended_countdown)
        self.assertIsNone(self._rule_2._extended_countdown)
        self.assertIsInstance(self._rule_extended._extended_countdown, CountdownJobControl)
        self.assertIsNone(self._rule_extended._extended_countdown.next_run_datetime)

    def test_countdown_end(self) -> None:
        """Test countdown end."""
        with unittest.mock.patch("habapp_rules.sensors.current_switch.send_if_different") as send_if_different_mock:
            self._rule_extended._countdown_end()

        send_if_different_mock.assert_called_once_with(self._rule_extended._config.items.switch, "OFF")

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
                item_state_change_event("Unittest_Current", test_case.current)

                assert_item_value("Unittest_Switch_1", test_case.expected_1)
                assert_item_value("Unittest_Switch_2", test_case.expected_2)

    def test_current_changed_with_extended_time(self) -> None:
        """Test current changed with extended time."""
        with unittest.mock.patch.object(self._rule_extended, "_extended_countdown") as countdown_mock:
            # below threshold
            item_state_change_event("Unittest_Current", 0.1)
            assert_item_value("Unittest_Switch_extended", None)
            countdown_mock.stop.assert_not_called()
            countdown_mock.reset.assert_not_called()

            # above threshold
            item_state_change_event("Unittest_Current", 0.3)
            assert_item_value("Unittest_Switch_extended", "ON")
            countdown_mock.stop.assert_called_once()
            countdown_mock.reset.assert_not_called()

            # below threshold
            countdown_mock.stop.reset_mock()
            item_state_change_event("Unittest_Current", 0.1)
            assert_item_value("Unittest_Switch_extended", "ON")
            countdown_mock.stop.assert_not_called()
            countdown_mock.reset.assert_called_once()
