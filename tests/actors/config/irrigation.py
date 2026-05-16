"""Test config models of irrigation rules."""

from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.actors.config.irrigation import IrrigationConfig, IrrigationItems
from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from tests.helper.oh_item import add_mock_item
from tests.helper.test_case_base import TestCaseBase


class TestIrrigationConfig(TestCaseBase):
    """Test IrrigationConfig class."""

    def test_model_validation(self) -> None:
        """Test model validation."""
        add_mock_item(SwitchItem, "Unittest_valve", None)
        add_mock_item(SwitchItem, "Unittest_active", None)
        add_mock_item(NumberItem, "Unittest_hour", None)
        add_mock_item(NumberItem, "Unittest_minute", None)
        add_mock_item(NumberItem, "Unittest_duration", None)
        add_mock_item(NumberItem, "Unittest_repetitions", None)
        add_mock_item(NumberItem, "Unittest_brake", None)

        with self.assertRaises(HabAppRulesConfigurationError):
            # config without repetitions
            IrrigationConfig(items=IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", brake="Unittest_brake"))

        with self.assertRaises(HabAppRulesConfigurationError):
            # config without brake
            IrrigationConfig(items=IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", repetitions="Unittest_repetitions"))
