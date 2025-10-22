"""Test KNX MQTT bridges."""

import collections
import unittest.mock

import HABApp.rule.rule

import habapp_rules.bridge.config.knx_mqtt
import habapp_rules.bridge.knx_mqtt
import tests.helper.oh_item
import tests.helper.test_case_base


class TestLight(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing Light rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_full_KNX_Dimmer_ctr", 0)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_full_KNX_Switch_ctr", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_full_MQTT_dimmer", 0)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_switch_KNX_Switch_ctr", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_switch_MQTT_dimmer", 0)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_dimmer_KNX_Dimmer_ctr", 0)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_dimmer_MQTT_dimmer", 0)

        config_full = habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(
            items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(mqtt_dimmer="Unittest_full_MQTT_dimmer", knx_switch_ctr="Unittest_full_KNX_Switch_ctr", knx_dimmer_ctr="Unittest_full_KNX_Dimmer_ctr")
        )

        config_switch = habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(mqtt_dimmer="Unittest_switch_MQTT_dimmer", knx_switch_ctr="Unittest_switch_KNX_Switch_ctr"))

        config_dimmer = habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(mqtt_dimmer="Unittest_dimmer_MQTT_dimmer", knx_dimmer_ctr="Unittest_dimmer_KNX_Dimmer_ctr"))

        self._knx_bridge_full = habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge(config_full)
        self._knx_bridge_switch = habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge(config_switch)
        self._knx_bridge_dimmer = habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge(config_dimmer)

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
        tests.helper.oh_item.set_state("Unittest_full_MQTT_dimmer", None)
        tests.helper.oh_item.set_state("Unittest_full_KNX_Switch_ctr", None)
        tests.helper.oh_item.set_state("Unittest_full_KNX_Dimmer_ctr", None)
        tests.helper.oh_item.set_state("Unittest_switch_MQTT_dimmer", None)
        tests.helper.oh_item.set_state("Unittest_switch_KNX_Switch_ctr", None)
        tests.helper.oh_item.set_state("Unittest_dimmer_MQTT_dimmer", None)
        tests.helper.oh_item.set_state("Unittest_dimmer_KNX_Dimmer_ctr", None)

        config_full = habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(
            items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(mqtt_dimmer="Unittest_full_MQTT_dimmer", knx_switch_ctr="Unittest_full_KNX_Switch_ctr", knx_dimmer_ctr="Unittest_full_KNX_Dimmer_ctr")
        )

        config_switch = habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(mqtt_dimmer="Unittest_switch_MQTT_dimmer", knx_switch_ctr="Unittest_switch_KNX_Switch_ctr"))

        config_dimmer = habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(mqtt_dimmer="Unittest_dimmer_MQTT_dimmer", knx_dimmer_ctr="Unittest_dimmer_KNX_Dimmer_ctr"))

        habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge(config_full)
        habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge(config_switch)
        habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge(config_dimmer)

    def test_knx_on_off(self) -> None:
        """Test ON/OFF from KNX."""
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)

        # ON via KNX
        tests.helper.oh_item.item_command_event("Unittest_full_KNX_Switch_ctr", "ON")
        self.assertEqual(100, self._knx_bridge_full._config.items.mqtt_dimmer.value)

        # OFF via KNX
        tests.helper.oh_item.item_command_event("Unittest_full_KNX_Switch_ctr", "OFF")
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)

        # 50 via KNX
        tests.helper.oh_item.item_command_event("Unittest_full_KNX_Dimmer_ctr", 50)
        self.assertEqual(50, self._knx_bridge_full._config.items.mqtt_dimmer.value)

        # 0 via KNX
        tests.helper.oh_item.item_command_event("Unittest_full_KNX_Dimmer_ctr", 0)
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)

    def test_knx_increase(self) -> None:
        """Test increase from KNX."""
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        tests.helper.oh_item.item_command_event("Unittest_full_KNX_Dimmer_ctr", "INCREASE")
        self.assertEqual(60, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        tests.helper.oh_item.item_command_event("Unittest_full_KNX_Dimmer_ctr", "INCREASE")
        self.assertEqual(100, self._knx_bridge_full._config.items.mqtt_dimmer.value)

    def test_knx_decrease(self) -> None:
        """Test decrease from KNX."""
        self._knx_bridge_full._config.items.mqtt_dimmer.oh_send_command(100)
        self.assertEqual(100, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        tests.helper.oh_item.item_command_event("Unittest_full_KNX_Dimmer_ctr", "DECREASE")
        self.assertEqual(30, self._knx_bridge_full._config.items.mqtt_dimmer.value)
        tests.helper.oh_item.item_command_event("Unittest_full_KNX_Dimmer_ctr", "DECREASE")
        self.assertEqual(0, self._knx_bridge_full._config.items.mqtt_dimmer.value)

    def test_knx_not_supported(self) -> None:
        """Test not supported command coming from KNX."""
        with unittest.mock.patch.object(self._knx_bridge_full, "_instance_logger") as logger_mock:
            tests.helper.oh_item.item_command_event("Unittest_full_KNX_Dimmer_ctr", "NotSupported")
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

                    tests.helper.oh_item.item_state_change_event("Unittest_full_MQTT_dimmer", test_case.send_value)
                    tests.helper.oh_item.item_state_change_event("Unittest_switch_MQTT_dimmer", test_case.send_value)
                    tests.helper.oh_item.item_state_change_event("Unittest_dimmer_MQTT_dimmer", test_case.send_value)

                    # full bridge (switch and dimmer item for KNX)
                    full_knx_dimmer_item_mock.oh_post_update.assert_called_once_with(test_case.expected_call_dimmer)
                    full_knx_switch_item_mock.oh_post_update.assert_called_once_with(test_case.expected_call_switch)

                    # partial bridges
                    switch_knx_switch_item_mock.oh_post_update.assert_called_once_with(test_case.expected_call_switch)
                    dimmer_knx_dimmer_item_mock.oh_post_update.assert_called_once_with(test_case.expected_call_dimmer)
