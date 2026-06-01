import unittest.mock

from HABApp.openhab.items import SwitchItem

from habapp_rules.network.config.wol import WolConfig, WolItems, WolParameter
from habapp_rules.network.wol import Wol
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_change_event,
)
from tests.helper.test_case_base import TestCaseBase


class TestWOL(TestCaseBase):
    """Test Wol rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(SwitchItem, "Unittest_WOL_min", None)
        add_mock_item(SwitchItem, "Unittest_WOL_max", None)

        self._config_min = WolConfig(items=WolItems(trigger_wol="Unittest_WOL_min"), parameter=WolParameter(mac_address="12:34:56:78:9a:ff"))
        self._config_max = WolConfig(items=WolItems(trigger_wol="Unittest_WOL_max"), parameter=WolParameter(mac_address="ab:cd:56:78:9a:ff", friendly_name="Some better name"))

        self._rule_min = Wol(self._config_min)
        self._rule_max = Wol(self._config_max)

    def test_trigger(self) -> None:
        """Test trigger of WOL."""
        # min
        with unittest.mock.patch("habapp_rules.network.wol.send_magic_packet") as send_magic_packet_mock, unittest.mock.patch.object(self._rule_min, "_instance_logger") as logger_mock:
            item_state_change_event("Unittest_WOL_min", "ON")
            send_magic_packet_mock.assert_called_once_with("12:34:56:78:9a:ff")
            logger_mock.info.assert_called_once_with("Triggered WOL for '12:34:56:78:9a:ff'")
            assert_item_value("Unittest_WOL_min", "OFF")

        # max
        with unittest.mock.patch("habapp_rules.network.wol.send_magic_packet") as send_magic_packet_mock, unittest.mock.patch.object(self._rule_max, "_instance_logger") as logger_mock:
            item_state_change_event("Unittest_WOL_max", "ON")
            send_magic_packet_mock.assert_called_once_with("ab:cd:56:78:9a:ff")
            logger_mock.info.assert_called_once_with("Triggered WOL for 'Some better name'")
            assert_item_value("Unittest_WOL_max", "OFF")
