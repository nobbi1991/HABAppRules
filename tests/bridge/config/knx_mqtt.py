"""Test config models for KNX / MQTT bridge rules."""

from HABApp.openhab.items import DimmerItem, SwitchItem

from habapp_rules.bridge.config.knx_mqtt import KnxMqttConfig, KnxMqttItems
from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from tests.helper.oh_item import add_mock_item
from tests.helper.test_case_base import TestCaseBase


class TestKnxMqttConfig(TestCaseBase):
    """Test KnxMqttConfig."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(DimmerItem, "Unittest_MQTT_dimmer", None)
        add_mock_item(DimmerItem, "Unittest_KNX_dimmer", None)
        add_mock_item(SwitchItem, "Unittest_KNX_switch", None)

    def test_validate_knx_items(self) -> None:
        """Test validate_knx_items."""
        # Both KNX items are given
        KnxMqttConfig(items=KnxMqttItems(mqtt_dimmer="Unittest_MQTT_dimmer", knx_switch_ctr="Unittest_KNX_switch", knx_dimmer_ctr="Unittest_KNX_dimmer"))

        # only KNX switch is given
        KnxMqttConfig(
            items=KnxMqttItems(
                mqtt_dimmer="Unittest_MQTT_dimmer",
                knx_switch_ctr="Unittest_KNX_switch",
            )
        )

        # only KNX dimmer is given
        KnxMqttConfig(items=KnxMqttItems(mqtt_dimmer="Unittest_MQTT_dimmer", knx_dimmer_ctr="Unittest_KNX_dimmer"))

        # no KNX item is given
        with self.assertRaises(HabAppRulesConfigurationError):
            KnxMqttConfig(
                items=KnxMqttItems(
                    mqtt_dimmer="Unittest_MQTT_dimmer",
                )
            )
