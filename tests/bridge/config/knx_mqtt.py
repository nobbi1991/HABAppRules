"""Test config models for KNX / MQTT bridge rules."""

import HABApp

import habapp_rules.bridge.config.knx_mqtt
import tests.helper.oh_item
import tests.helper.test_case_base


class TestKnxMqttConfig(tests.helper.test_case_base.TestCaseBase):
    """Test KnxMqttConfig."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_MQTT_dimmer", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_KNX_dimmer", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_KNX_switch", None)

    def test_validate_knx_items(self) -> None:
        """Test validate_knx_items."""
        # Both KNX items are given
        habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(mqtt_dimmer="Unittest_MQTT_dimmer", knx_switch_ctr="Unittest_KNX_switch", knx_dimmer_ctr="Unittest_KNX_dimmer"))

        # only KNX switch is given
        habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(
            items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(
                mqtt_dimmer="Unittest_MQTT_dimmer",
                knx_switch_ctr="Unittest_KNX_switch",
            )
        )

        # only KNX dimmer is given
        habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(mqtt_dimmer="Unittest_MQTT_dimmer", knx_dimmer_ctr="Unittest_KNX_dimmer"))

        # no KNX item is given
        with self.assertRaises(ValueError):
            habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig(
                items=habapp_rules.bridge.config.knx_mqtt.KnxMqttItems(
                    mqtt_dimmer="Unittest_MQTT_dimmer",
                )
            )
