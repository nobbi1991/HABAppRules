"""Tests for Watchdog Rule."""

import unittest.mock

import HABApp.openhab.items

import habapp_rules.system.item_watchdog
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.system.config.item_watchdog import WatchdogConfig, WatchdogItems, WatchdogParameter


class TestWatchdog(tests.helper.test_case_base.TestCaseBase):
    """Tests for Watchdog Rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Number_Warning", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_Warning", None)

        self._watchdog_number = habapp_rules.system.item_watchdog.ItemWatchdog(WatchdogConfig(items=WatchdogItems(observed="Unittest_Number", warning="Unittest_Number_Warning")))

        self._watchdog_switch = habapp_rules.system.item_watchdog.ItemWatchdog(WatchdogConfig(items=WatchdogItems(observed="Unittest_Switch", warning="Unittest_Switch_Warning"), parameter=WatchdogParameter(timeout=10)))

    def test_cb_observed_state_updated(self) -> None:
        """Callback which is called if the observed item was updated."""
        with unittest.mock.patch.object(self._watchdog_number, "_countdown") as number_countdown_mock, unittest.mock.patch.object(self._watchdog_switch, "_countdown") as switch_countdown_mock:
            tests.helper.oh_item.item_state_event("Unittest_Number", 42)
            number_countdown_mock.reset.assert_called_once()
            switch_countdown_mock.reset.assert_not_called()
            tests.helper.oh_item.assert_value("Unittest_Number_Warning", "OFF")
            tests.helper.oh_item.assert_value("Unittest_Switch_Warning", None)

            tests.helper.oh_item.item_state_event("Unittest_Switch", "OFF")
            number_countdown_mock.reset.assert_called_once()
            switch_countdown_mock.reset.assert_called_once()
            tests.helper.oh_item.assert_value("Unittest_Number_Warning", "OFF")
            tests.helper.oh_item.assert_value("Unittest_Switch_Warning", "OFF")
