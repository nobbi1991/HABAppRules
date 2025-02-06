"""Test config models of irrigation rules."""

import HABApp
import pydantic

import habapp_rules.actors.config.irrigation
import tests.helper.oh_item
import tests.helper.test_case_base


class TestIrrigationConfig(tests.helper.test_case_base.TestCaseBase):
    """Test IrrigationConfig class."""

    def test_model_validation(self) -> None:
        """Test model validation."""
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_valve", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_active", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_hour", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_minute", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_duration", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_repetitions", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_brake", None)

        with self.assertRaises(pydantic.ValidationError):
            # config without repetitions
            habapp_rules.actors.config.irrigation.IrrigationConfig(
                items=habapp_rules.actors.config.irrigation.IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", brake="Unittest_brake")
            )

        with self.assertRaises(pydantic.ValidationError):
            # config without brake
            habapp_rules.actors.config.irrigation.IrrigationConfig(
                items=habapp_rules.actors.config.irrigation.IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", repetitions="Unittest_repetitions")
            )
