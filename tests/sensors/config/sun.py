"""Test config models for sun rules."""

import unittest

from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.sensors.config.sun import BrightnessConfig, BrightnessItems, BrightnessParameter, SunPositionWindow, TemperatureDifferenceItems
from tests.helper.oh_item import (
    add_mock_item,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBase


class TestTemperatureDifferenceItems(TestCaseBase):
    """Test TemperatureDifferenceItems."""

    def test_validate_temperature_items(self) -> None:
        """Test validate_temperature_items."""
        add_mock_item(SwitchItem, "Unittest_Output", None)
        add_mock_item(NumberItem, "Unittest_Temperature_1", None)
        add_mock_item(NumberItem, "Unittest_Temperature_2", None)
        add_mock_item(NumberItem, "Unittest_Temperature_3", None)

        # no item is given
        with self.assertRaises(HabAppRulesConfigurationError):
            TemperatureDifferenceItems(temperatures=[], output="Unittest_Output")

        # single item is given
        with self.assertRaises(HabAppRulesConfigurationError):
            TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1"], output="Unittest_Output")

        # two items are given
        TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1", "Unittest_Temperature_2"], output="Unittest_Output")

        # three items are given
        TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1", "Unittest_Temperature_2", "Unittest_Temperature_3"], output="Unittest_Output")


class TestConfigBase(TestCaseBase):
    """Test ConfigBase."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)
        add_mock_item(NumberItem, "Unittest_Brightness", None)
        add_mock_item(SwitchItem, "Unittest_Output", None)
        add_mock_item(NumberItem, "Unittest_Threshold", None)

    def test_validate_threshold(self) -> None:
        """Test validate_threshold."""
        # item NOT given | parameter NOT given
        with self.assertRaises(HabAppRulesConfigurationError):
            BrightnessConfig(items=BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output"))

        # item NOT given | parameter given
        BrightnessConfig(items=BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output"), parameter=BrightnessParameter(threshold=42))

        # item given | parameter NOT given
        BrightnessConfig(items=BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output", threshold="Unittest_Threshold"))

        # item given | parameter given
        with self.assertRaises(HabAppRulesConfigurationError):
            BrightnessConfig(items=BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output", threshold="Unittest_Threshold"), parameter=BrightnessParameter(threshold=42))

    def test_threshold_property(self) -> None:
        """Test threshold property."""
        # with parameter
        config = BrightnessConfig(items=BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output"), parameter=BrightnessParameter(threshold=42))
        self.assertEqual(42, config.threshold)

        # with item | value is None
        config = BrightnessConfig(items=BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output", threshold="Unittest_Threshold"))
        self.assertEqual(float("inf"), config.threshold)

        # set value
        set_item_state("Unittest_Threshold", 99)
        self.assertEqual(99, config.threshold)


class TestSunPositionWindow(unittest.TestCase):
    """Tests cases for testing the sun position filter."""

    def test_init(self) -> None:
        """Test __init__."""
        # normal init
        expected_result = SunPositionWindow(10, 80, 2, 20)
        self.assertEqual(expected_result, SunPositionWindow(10, 80, 2, 20))

        # init without elevation
        expected_result = SunPositionWindow(10, 80, 0, 90)
        self.assertEqual(expected_result, SunPositionWindow(10, 80))

        # init with min > max
        expected_result = SunPositionWindow(10, 80, 2, 20)
        self.assertEqual(expected_result, SunPositionWindow(80, 10, 20, 2))
