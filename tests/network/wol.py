import unittest.mock

import HABApp

import habapp_rules.network.wol
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.network.config.wol import WolConfig, WolItems, WolParameter


class TestWOL(tests.helper.test_case_base.TestCaseBase):
    """Test Wol rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_WOL_min", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_WOL_max", None)

        self._config_min = WolConfig(items=WolItems(trigger_wol="Unittest_WOL_min"), parameter=WolParameter(mac_address="12:34:56:78:9a:ff"))
        self._config_max = WolConfig(items=WolItems(trigger_wol="Unittest_WOL_max"), parameter=WolParameter(mac_address="ab:cd:56:78:9a:ff", friendly_name="Some better name"))

        self._rule_min = habapp_rules.network.wol.Wol(self._config_min)
        self._rule_max = habapp_rules.network.wol.Wol(self._config_max)

    def test_trigger(self) -> None:
        """Test trigger of WOL."""
        # min
        with unittest.mock.patch("habapp_rules.network.wol.send_magic_packet") as send_magic_packet_mock, unittest.mock.patch("habapp_rules.network.wol.LOGGER") as logger_mock:
            tests.helper.oh_item.item_state_change_event("Unittest_WOL_min", "ON")
            send_magic_packet_mock.assert_called_once_with("12:34:56:78:9a:ff")
            logger_mock.info.assert_called_once_with("Triggered WOL for '12:34:56:78:9a:ff'")
            tests.helper.oh_item.assert_value("Unittest_WOL_min", "OFF")

        # max
        with unittest.mock.patch("habapp_rules.network.wol.send_magic_packet") as send_magic_packet_mock, unittest.mock.patch("habapp_rules.network.wol.LOGGER") as logger_mock:
            tests.helper.oh_item.item_state_change_event("Unittest_WOL_max", "ON")
            send_magic_packet_mock.assert_called_once_with("ab:cd:56:78:9a:ff")
            logger_mock.info.assert_called_once_with("Triggered WOL for 'Some better name'")
            tests.helper.oh_item.assert_value("Unittest_WOL_max", "OFF")
