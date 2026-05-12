"""Test KNX MQTT bridges."""

import collections
import unittest.mock

from HABApp.openhab.items import DimmerItem, SwitchItem

from habapp_rules.bridge.config.knx_mqtt import KnxMqttConfig, KnxMqttItems
from habapp_rules.bridge.knx_mqtt import KnxMqttDimmerBridge
from tests.helper.oh_item import add_mock_item, item_command_event, item_state_change_event, set_item_state
from tests.helper.test_case_base import TestCaseBase


class TestLight(TestCaseBase):
    """Tests cases for testing Light rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(DimmerItem, "Unittest_full_KNX_Dimmer_ctr", 0)
        add_mock_item(SwitchItem, "Unittest_full_KNX_Switch_ctr", "OFF")
        add_mock_item(DimmerItem, "Unittest_full_MQTT_dimmer", 0)

        add_mock_item(SwitchItem, "Unittest_switch_KNX_Switch_ctr", "OFF")
        add_mock_item(DimmerItem, "Unittest_switch_MQTT_dimmer", 0)

        add_mock_item(DimmerItem, "Unittest_dimmer_KNX_Dimmer_ctr", 0)
        add_mock_item(DimmerItem, "Unittest_dimmer_MQTT_dimmer", 0)

        config_full = KnxMqttConfig(items=KnxMqttItems(mqtt_dimmer="Unittest_full_MQTT_dimmer", knx_switch_ctr="Unittest_full_KNX_Switch_ctr", knx_dimmer_ctr="Unittest_full_KNX_Dimmer_ctr"))

        config_switch = KnxMqttConfig(items=KnxMqttItems(mqtt_dimmer="Unittest_switch_MQTT_dimmer", knx_switch_ctr="Unittest_switch_KNX_Switch_ctr"))

        config_dimmer = KnxMqttConfig(items=KnxMqttItems(mqtt_dimmer="Unittest_dimmer_MQTT_dimmer", knx_dimmer_ctr="Unittest_dimmer_KNX_Dimmer_ctr"))

        self._knx_bridge_full = KnxMqttDimmerBridge(config_full)
        self._knx_bridge_switch = KnxMqttDimmerBridge(config_switch)
        self._knx_bridge_dimmer = KnxMqttDimmerBridge(config_dimmer)

    def test__init__(self) -> None:
        """Test __init__."""
        self.assertIsNotNone(self._knx_bridge_full._config.items.knx_switch_ctr)
        self.assertIsNotNone(self._knx_bridge_full._config.items.knx_dimmer_ctr)

        self.assertIsNotNone(self._knx_bridge_switch._config.items.knx_switch_ctr)
        self.assertIsNone(self._knx_bridge_switch._config.items.knx_dimmer_ctr)

        self.assertIsNone(self._knx_bridge_dimmer._config.items.knx_switch_ctr)
        self.assertIsNotNone(self._knx_bridge_dimmer._config.items.knx_dimmer_ctr)

    def test_init_with_none(self) -> None:
        """Test __init__ with None values."""
        set_item_state("Unittest_full_MQTT_dimmer", None)
        set_item_state("Unittest_full_KNX_Switch_ctr", None)
        set_item_state("Unittest_full_KNX_Dimmer_ctr", None)
        set_item_state("Unittest_switch_MQTT_dimmer", None)
        set_item_state("Unittest_switch_KNX_Switch_ctr", None)
        set_item_state("Unittest_dimmer_MQTT_dimmer", None)
        set_item_state("Unittest_dimmer_KNX_Dimmer_ctr", None)

        config_full = KnxMqttConfig(items=KnxMqttItems(mqtt_dimmer="Unittest_full_MQTT_dimmer", knx_switch_ctr="Unittest_full_KNX_Switch_ctr", knx_dimmer_ctr="Unittest_full_KNX_Dimmer_ctr"))

        config_switch = KnxMqttConfig(items=KnxMqttItems(mqtt_dimmer="Unittest_switch_MQTT_dimmer", knx_switch_ctr="Unittest_switch_KNX_Switch_ctr"))

        config_dimmer = KnxMqttConfig(items=KnxMqttItems(mqtt_dimmer="Unittest_dimmer_MQTT_dimmer", knx_dimmer_ctr="Unittest_dimmer_KNX_Dimmer_ctr"))

        KnxMqttDimmerBridge(config_full)
        KnxMqttDimmerBridge(config_switch)
        KnxMqttDimmerBridge(config_dimmer)

    def test_knx_on_off(self) -> None:
        """Test ON/OFF from KNX."""
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)

        # ON via KNX
        item_command_event("Unittest_full_KNX_Switch_ctr", "ON")
        self.assertEqual(100, self._knx_bridge_full._config.items.mqtt_dimmer.value)

        # OFF via KNX
        item_command_event("Unittest_full_KNX_Switch_ctr", "OFF")
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)

        # 50 via KNX
        item_command_event("Unittest_full_KNX_Dimmer_ctr", 50)
        self.assertEqual(50, self._knx_bridge_full._config.items.mqtt_dimmer.value)

        # 0 via KNX
        item_command_event("Unittest_full_KNX_Dimmer_ctr", 0)
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)

    def test_knx_increase(self) -> None:
        """Test increase from KNX."""
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        item_command_event("Unittest_full_KNX_Dimmer_ctr", "INCREASE")
        self.assertEqual(60, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        item_command_event("Unittest_full_KNX_Dimmer_ctr", "INCREASE")
        self.assertEqual(100, self._knx_bridge_full._config.items.mqtt_dimmer.value)

    def test_knx_decrease(self) -> None:
        """Test decrease from KNX."""
        self._knx_bridge_full._config.items.mqtt_dimmer.oh_send_command(100)
        self.assertEqual(100, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        item_command_event("Unittest_full_KNX_Dimmer_ctr", "DECREASE")
        self.assertEqual(30, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        item_command_event("Unittest_full_KNX_Dimmer_ctr", "DECREASE")
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)

    def test_knx_not_supported(self) -> None:
        """Test not supported command coming from KNX."""
        with unittest.mock.patch.object(self._knx_bridge_full, "_instance_logger") as logger_mock:
            item_command_event("Unittest_full_KNX_Dimmer_ctr", "NotSupported")
            logger_mock.error.assert_called_once_with("command 'NotSupported' ist not supported!")

    def test_mqtt_events(self) -> None:
        """Test if KNX item is updated correctly if MQTT item changed."""
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        TestCase = collections.namedtuple("TestCase", "send_value, expected_call_dimmer, expected_call_switch")

        test_cases = [TestCase(70, 70, "ON"), TestCase(100, 100, "ON"), TestCase(1, 1, "ON"), TestCase(0, 0, "OFF")]

        with (
            unittest.mock.patch.object(self._knx_bridge_full._config.items, "knx_dimmer_ctr") as full_knx_dimmer_item_mock,
            unittest.mock.patch.object(self._knx_bridge_full._config.items, "knx_switch_ctr") as full_knx_switch_item_mock,
            unittest.mock.patch.object(self._knx_bridge_switch._config.items, "knx_switch_ctr") as switch_knx_switch_item_mock,
            unittest.mock.patch.object(self._knx_bridge_dimmer._config.items, "knx_dimmer_ctr") as dimmer_knx_dimmer_item_mock,
        ):
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    full_knx_dimmer_item_mock.oh_post_update.reset_mock()
                    full_knx_switch_item_mock.oh_post_update.reset_mock()
                    switch_knx_switch_item_mock.oh_post_update.reset_mock()
                    dimmer_knx_dimmer_item_mock.oh_post_update.reset_mock()

                    item_state_change_event("Unittest_full_MQTT_dimmer", test_case.send_value)
                    item_state_change_event("Unittest_switch_MQTT_dimmer", test_case.send_value)
                    item_state_change_event("Unittest_dimmer_MQTT_dimmer", test_case.send_value)

                    # full bridge (switch and dimmer item for KNX)
                    full_knx_dimmer_item_mock.oh_post_update.assert_called_once_with(test_case.expected_call_dimmer)
                    full_knx_switch_item_mock.oh_post_update.assert_called_once_with(test_case.expected_call_switch)

                    # partial bridges
                    switch_knx_switch_item_mock.oh_post_update.assert_called_once_with(test_case.expected_call_switch)
                    dimmer_knx_dimmer_item_mock.oh_post_update.assert_called_once_with(test_case.expected_call_dimmer)
