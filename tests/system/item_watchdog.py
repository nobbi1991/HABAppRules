"""Tests for Watchdog Rule."""

import unittest.mock

from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.system.config.item_watchdog import WatchdogConfig, WatchdogItems, WatchdogParameter
from habapp_rules.system.item_watchdog import ItemWatchdog
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_event,
)
from tests.helper.test_case_base import TestCaseBase


class TestWatchdog(TestCaseBase):
    """Tests for Watchdog Rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Number", None)
        add_mock_item(SwitchItem, "Unittest_Switch", None)
        add_mock_item(SwitchItem, "Unittest_Number_Warning", None)
        add_mock_item(SwitchItem, "Unittest_Switch_Warning", None)

        self._watchdog_number = ItemWatchdog(WatchdogConfig(items=WatchdogItems(observed="Unittest_Number", warning="Unittest_Number_Warning")))

        self._watchdog_switch = ItemWatchdog(WatchdogConfig(items=WatchdogItems(observed="Unittest_Switch", warning="Unittest_Switch_Warning"), parameter=WatchdogParameter(timeout=10)))

    def test_cb_observed_state_updated(self) -> None:
        """Callback which is called if the observed item was updated."""
        with unittest.mock.patch.object(self._watchdog_number, "_countdown") as number_countdown_mock, unittest.mock.patch.object(self._watchdog_switch, "_countdown") as switch_countdown_mock:
            item_state_event("Unittest_Number", 42)
            number_countdown_mock.reset.assert_called_once()
            switch_countdown_mock.reset.assert_not_called()
            assert_item_value("Unittest_Number_Warning", "OFF")
            assert_item_value("Unittest_Switch_Warning", None)

            item_state_event("Unittest_Switch", "OFF")
            number_countdown_mock.reset.assert_called_once()
            switch_countdown_mock.reset.assert_called_once()
            assert_item_value("Unittest_Number_Warning", "OFF")
            assert_item_value("Unittest_Switch_Warning", "OFF")
