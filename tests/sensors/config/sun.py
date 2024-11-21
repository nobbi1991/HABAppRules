"""Test config models for sun rules."""

import unittest

import HABApp
import pydantic

import habapp_rules.core.exceptions
import habapp_rules.sensors.config.sun
import tests.helper.oh_item
import tests.helper.test_case_base


class TestTemperatureDifferenceItems(tests.helper.test_case_base.TestCaseBase):
    """Test TemperatureDifferenceItems."""

    def test_validate_temperature_items(self) -> None:
        """Test validate_temperature_items."""
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_3", None)

        # no item is given
        with self.assertRaises(pydantic.ValidationError):
            habapp_rules.sensors.config.sun.TemperatureDifferenceItems(temperatures=[], output="Unittest_Output")

        # single item is given
        with self.assertRaises(pydantic.ValidationError):
            habapp_rules.sensors.config.sun.TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1"], output="Unittest_Output")

        # two items are given
        habapp_rules.sensors.config.sun.TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1", "Unittest_Temperature_2"], output="Unittest_Output")

        # three items are given
        habapp_rules.sensors.config.sun.TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1", "Unittest_Temperature_2", "Unittest_Temperature_3"], output="Unittest_Output")


class TestConfigBase(tests.helper.test_case_base.TestCaseBase):
    """Test ConfigBase."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Threshold", None)

    def test_validate_threshold(self) -> None:
        """Test validate_threshold."""
        # item NOT given | parameter NOT given
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.sensors.config.sun.BrightnessConfig(items=habapp_rules.sensors.config.sun.BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output"))

        # item NOT given | parameter given
        habapp_rules.sensors.config.sun.BrightnessConfig(items=habapp_rules.sensors.config.sun.BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output"), parameter=habapp_rules.sensors.config.sun.BrightnessParameter(threshold=42))

        # item given | parameter NOT given
        habapp_rules.sensors.config.sun.BrightnessConfig(items=habapp_rules.sensors.config.sun.BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output", threshold="Unittest_Threshold"))

        # item given | parameter given
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.sensors.config.sun.BrightnessConfig(
                items=habapp_rules.sensors.config.sun.BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output", threshold="Unittest_Threshold"), parameter=habapp_rules.sensors.config.sun.BrightnessParameter(threshold=42)
            )

    def test_threshold_property(self) -> None:
        """Test threshold property."""
        # with parameter
        config = habapp_rules.sensors.config.sun.BrightnessConfig(
            items=habapp_rules.sensors.config.sun.BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output"), parameter=habapp_rules.sensors.config.sun.BrightnessParameter(threshold=42)
        )
        self.assertEqual(42, config.threshold)

        # with item | value is None
        config = habapp_rules.sensors.config.sun.BrightnessConfig(items=habapp_rules.sensors.config.sun.BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output", threshold="Unittest_Threshold"))
        self.assertEqual(float("inf"), config.threshold)

        # set value
        tests.helper.oh_item.set_state("Unittest_Threshold", 99)
        self.assertEqual(99, config.threshold)


class TestSunPositionWindow(unittest.TestCase):
    """Tests cases for testing the sun position filter."""

    def test_init(self) -> None:
        """Test __init__."""
        # normal init
        expected_result = habapp_rules.sensors.config.sun.SunPositionWindow(10, 80, 2, 20)
        self.assertEqual(expected_result, habapp_rules.sensors.config.sun.SunPositionWindow(10, 80, 2, 20))

        # init without elevation
        expected_result = habapp_rules.sensors.config.sun.SunPositionWindow(10, 80, 0, 90)
        self.assertEqual(expected_result, habapp_rules.sensors.config.sun.SunPositionWindow(10, 80))

        # init with min > max
        expected_result = habapp_rules.sensors.config.sun.SunPositionWindow(10, 80, 2, 20)
        self.assertEqual(expected_result, habapp_rules.sensors.config.sun.SunPositionWindow(80, 10, 20, 2))
