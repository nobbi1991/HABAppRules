"""Tests for sun sensors."""

import collections
import unittest.mock

from HABApp.openhab.items import NumberItem, OpenhabItem, StringItem, SwitchItem

from habapp_rules.sensors.config.sun import (
    BrightnessConfig,
    BrightnessItems,
    BrightnessParameter,
    SunPositionConfig,
    SunPositionItems,
    SunPositionParameter,
    SunPositionWindow,
    TemperatureDifferenceConfig,
    TemperatureDifferenceItems,
    TemperatureDifferenceParameter,
    WinterFilterConfig,
    WinterFilterItems,
)
from habapp_rules.sensors.sun import SensorBrightness, SensorTemperatureDifference, SunPositionFilter, WinterFilter
from habapp_rules.system import PresenceState
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_change_event,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBase


class TestSensorTemperatureDifference(TestCaseBase):
    """Tests cases for testing sun sensor 'temp_diff' rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Temperature_1", None)
        add_mock_item(NumberItem, "Unittest_Temperature_2", None)
        add_mock_item(SwitchItem, "Unittest_Output_Temperature", None)
        add_mock_item(NumberItem, "Unittest_Threshold_Temperature", None)
        add_mock_item(NumberItem, "H_Temperature_diff_for_Unittest_Output_Temperature", None)
        add_mock_item(NumberItem, "H_Temperature_diff_for_Unittest_Output_Temperature_filtered", None)

        config = TemperatureDifferenceConfig(items=TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1", "Unittest_Temperature_2"], output="Unittest_Output_Temperature", threshold="Unittest_Threshold_Temperature"))

        with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True), unittest.mock.patch("habapp_rules.common.filter.ExponentialFilter"):
            self._sensor = SensorTemperatureDifference(config)

    def test_init(self) -> None:
        """Test __init__."""
        self.assertEqual(float("inf"), self._sensor._hysteresis_switch._threshold)
        self.assertEqual("H_Temperature_diff_for_Unittest_Output_Temperature", self._sensor._item_temp_diff.name)

    def test_init_with_fixed_threshold(self) -> None:
        """Test __init__ with fixed threshold value."""
        config = TemperatureDifferenceConfig(
            items=TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1", "Unittest_Temperature_2"], output="Unittest_Output_Temperature"),
            parameter=TemperatureDifferenceParameter(threshold=42),
        )

        with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True), unittest.mock.patch("habapp_rules.common.filter.ExponentialFilter"):
            sensor = SensorTemperatureDifference(config)
        self.assertEqual(42, sensor._hysteresis_switch._threshold)

    def test_cb_threshold(self) -> None:
        """Test _cb_threshold."""
        item_state_change_event("Unittest_Threshold_Temperature", 20)
        self.assertEqual(20, self._sensor._hysteresis_switch._threshold)

    def test_temp_diff(self) -> None:
        """Test if temperature difference is calculated correctly."""
        temp_diff_item = OpenhabItem.get_item("H_Temperature_diff_for_Unittest_Output_Temperature")
        self.assertEqual(None, temp_diff_item.value)

        # update temperature 1
        item_state_change_event("Unittest_Temperature_1", 20)
        self.assertEqual(None, temp_diff_item.value)

        # update temperature 2
        item_state_change_event("Unittest_Temperature_2", 21)
        self.assertEqual(1, temp_diff_item.value)

        # update temperature 2
        item_state_change_event("Unittest_Temperature_2", 18)
        self.assertEqual(2, temp_diff_item.value)

        # update temperature 1
        item_state_change_event("Unittest_Temperature_1", -20)
        self.assertEqual(38, temp_diff_item.value)

        # update temperature 2
        item_state_change_event("Unittest_Temperature_2", -25)
        self.assertEqual(5, temp_diff_item.value)

    def test_threshold_behavior(self) -> None:
        """Test overall behavior."""
        output_item = OpenhabItem.get_item("Unittest_Output_Temperature")
        self.assertEqual(None, output_item.value)

        # set threshold to 10
        self._sensor._hysteresis_switch.set_threshold_on(10)

        # update temp_diff to 10
        item_state_change_event("H_Temperature_diff_for_Unittest_Output_Temperature_filtered", 10)
        self.assertEqual("ON", output_item.value)

        # update temp_diff to 9.9
        item_state_change_event("H_Temperature_diff_for_Unittest_Output_Temperature_filtered", 9.9)
        self.assertEqual("OFF", output_item.value)

        # update temp_diff to 8
        item_state_change_event("H_Temperature_diff_for_Unittest_Output_Temperature_filtered", 8)
        self.assertEqual("OFF", output_item.value)


class TestSensorBrightness(TestCaseBase):
    """Tests cases for testing sun sensor 'brightness' rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Brightness", None)
        add_mock_item(SwitchItem, "Unittest_Output_Brightness", None)
        add_mock_item(NumberItem, "Unittest_Threshold_Brightness", None)
        add_mock_item(NumberItem, "H_Unittest_Brightness_filtered", None)

        config = BrightnessConfig(items=BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output_Brightness", threshold="Unittest_Threshold_Brightness"))

        with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True), unittest.mock.patch("habapp_rules.common.filter.ExponentialFilter"):
            self._sensor = SensorBrightness(config)

    def test_init(self) -> None:
        """Test __init__."""
        self.assertEqual(float("inf"), self._sensor._hysteresis_switch._threshold)

    def test_init_with_fixed_threshold(self) -> None:
        """Test __init__ with fixed threshold value."""
        config = BrightnessConfig(
            items=BrightnessItems(
                brightness="Unittest_Brightness",
                output="Unittest_Output_Brightness",
            ),
            parameter=BrightnessParameter(threshold=42),
        )

        with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True), unittest.mock.patch("habapp_rules.common.filter.ExponentialFilter"):
            sensor = SensorBrightness(config)
        self.assertEqual(42, sensor._hysteresis_switch._threshold)

    def test_cb_threshold(self) -> None:
        """Test _cb_threshold."""
        item_state_change_event("Unittest_Threshold_Brightness", 42000)
        self.assertEqual(42000, self._sensor._hysteresis_switch._threshold)

    def test_threshold_behavior(self) -> None:
        """Test overall behavior."""
        output_item = OpenhabItem.get_item("Unittest_Output_Brightness")
        self.assertEqual(None, output_item.value)

        # set threshold to 1000
        self._sensor._hysteresis_switch.set_threshold_on(1000)

        # update temp_diff to 1000
        item_state_change_event("H_Unittest_Brightness_filtered", 1000)
        self.assertEqual("ON", output_item.value)

        # update temp_diff to 999
        item_state_change_event("H_Unittest_Brightness_filtered", 999)
        self.assertEqual("OFF", output_item.value)

        # update temp_diff to 800
        item_state_change_event("H_Unittest_Brightness_filtered", 800)
        self.assertEqual("OFF", output_item.value)


class TestSunPositionFilter(TestCaseBase):
    """Tests cases for testing the sun position filter."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(SwitchItem, "Unittest_Input_1", None)
        add_mock_item(SwitchItem, "Unittest_Output_1", None)

        add_mock_item(SwitchItem, "Unittest_Input_2", None)
        add_mock_item(SwitchItem, "Unittest_Output_2", None)

        add_mock_item(NumberItem, "Unittest_Azimuth", 1000)
        add_mock_item(NumberItem, "Unittest_Elevation", 1000)

        self.position_window_1 = SunPositionWindow(10, 80, 2, 20)
        self.position_window_2 = SunPositionWindow(100, 120)

        config_1 = SunPositionConfig(
            items=SunPositionItems(
                azimuth="Unittest_Azimuth",
                elevation="Unittest_Elevation",
                input="Unittest_Input_1",
                output="Unittest_Output_1",
            ),
            parameter=SunPositionParameter(sun_position_window=self.position_window_1),
        )
        config_2 = SunPositionConfig(
            items=SunPositionItems(
                azimuth="Unittest_Azimuth",
                elevation="Unittest_Elevation",
                input="Unittest_Input_2",
                output="Unittest_Output_2",
            ),
            parameter=SunPositionParameter(sun_position_window=[self.position_window_1, self.position_window_2]),
        )

        self._filter_1 = SunPositionFilter(config_1)
        self._filter_2 = SunPositionFilter(config_2)

    def test_init(self) -> None:
        """Test __init__."""
        self.assertEqual([self.position_window_1], self._filter_1._config.parameter.sun_position_windows)
        self.assertEqual([self.position_window_1, self.position_window_2], self._filter_2._config.parameter.sun_position_windows)

    def test_filter(self) -> None:
        """Test if filter is working correctly."""
        TestCase = collections.namedtuple("TestCase", "azimuth, elevation, input, output_1, output_2")

        test_cases = [
            TestCase(0, 0, "OFF", "OFF", "OFF"),
            TestCase(0, 10, "OFF", "OFF", "OFF"),
            TestCase(50, 0, "OFF", "OFF", "OFF"),
            TestCase(50, 10, "OFF", "OFF", "OFF"),
            TestCase(0, 0, "ON", "OFF", "OFF"),
            TestCase(0, 10, "ON", "OFF", "OFF"),
            TestCase(50, 0, "ON", "OFF", "OFF"),
            TestCase(50, 10, "ON", "ON", "ON"),
            TestCase(0, 0, "OFF", "OFF", "OFF"),
            TestCase(0, 10, "OFF", "OFF", "OFF"),
            TestCase(110, 0, "OFF", "OFF", "OFF"),
            TestCase(110, 10, "OFF", "OFF", "OFF"),
            TestCase(0, 0, "ON", "OFF", "OFF"),
            TestCase(0, 10, "ON", "OFF", "OFF"),
            TestCase(110, 0, "ON", "OFF", "ON"),
            TestCase(110, 10, "ON", "OFF", "ON"),
            TestCase(50, None, "OFF", "OFF", "OFF"),
            TestCase(None, 10, "OFF", "OFF", "OFF"),
            TestCase(None, None, "OFF", "OFF", "OFF"),
            TestCase(50, None, "ON", "ON", "ON"),
            TestCase(None, 10, "ON", "ON", "ON"),
            TestCase(None, None, "ON", "ON", "ON"),
        ]

        item_output_1 = OpenhabItem.get_item("Unittest_Output_1")
        item_output_2 = OpenhabItem.get_item("Unittest_Output_2")

        with unittest.mock.patch.object(self._filter_1, "_instance_logger") as log_1_mock, unittest.mock.patch.object(self._filter_2, "_instance_logger") as log_2_mock:
            for test_case in test_cases:
                log_1_mock.reset_mock()
                log_2_mock.reset_mock()

                set_item_state("Unittest_Input_1", test_case.input)
                set_item_state("Unittest_Input_2", test_case.input)

                item_state_change_event("Unittest_Elevation", test_case.elevation)
                item_state_change_event("Unittest_Azimuth", test_case.azimuth)

                self.assertEqual(test_case.output_1, item_output_1.value)
                self.assertEqual(test_case.output_2, item_output_2.value)

                if test_case.azimuth is None or test_case.elevation is None:
                    log_1_mock.warning.assert_called_once()
                    log_2_mock.warning.assert_called_once()
                else:
                    log_1_mock.warning.assert_not_called()
                    log_2_mock.warning.assert_not_called()


class TestWinterFilter(TestCaseBase):
    """Tests cases WinterFilter rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(SwitchItem, "Unittest_Sun", None)
        add_mock_item(SwitchItem, "Unittest_Winter", None)
        add_mock_item(StringItem, "Unittest_Presence_state", None)

        add_mock_item(SwitchItem, "Unittest_Output_1", None)
        add_mock_item(SwitchItem, "Unittest_Output_2", None)

        config_full = WinterFilterConfig(
            items=WinterFilterItems(
                sun="Unittest_Sun",
                heating_active="Unittest_Winter",
                presence_state="Unittest_Presence_state",
                output="Unittest_Output_1",
            )
        )

        config_only_heating = WinterFilterConfig(
            items=WinterFilterItems(
                sun="Unittest_Sun",
                heating_active="Unittest_Winter",
                output="Unittest_Output_2",
            )
        )

        self._rule_full = WinterFilter(config_full)
        self._rule_winter = WinterFilter(config_only_heating)

    def test_filter(self) -> None:
        """Test WinterFilter rule."""
        TestCase = collections.namedtuple("TestCase", "sun, heating_active, presence_state, out_full, out_winter")

        test_cases = [
            # sun off
            TestCase(sun="OFF", heating_active="OFF", presence_state=PresenceState.PRESENCE, out_full="OFF", out_winter="OFF"),
            TestCase(sun="OFF", heating_active="OFF", presence_state=PresenceState.ABSENCE, out_full="OFF", out_winter="OFF"),
            TestCase(sun="OFF", heating_active="ON", presence_state=PresenceState.PRESENCE, out_full="OFF", out_winter="OFF"),
            TestCase(sun="OFF", heating_active="ON", presence_state=PresenceState.ABSENCE, out_full="OFF", out_winter="OFF"),
            # sun on
            TestCase(sun="ON", heating_active="OFF", presence_state=PresenceState.PRESENCE, out_full="ON", out_winter="ON"),
            TestCase(sun="ON", heating_active="OFF", presence_state=PresenceState.ABSENCE, out_full="ON", out_winter="ON"),
            TestCase(sun="ON", heating_active="ON", presence_state=PresenceState.PRESENCE, out_full="ON", out_winter="OFF"),
            TestCase(sun="ON", heating_active="ON", presence_state=PresenceState.ABSENCE, out_full="OFF", out_winter="OFF"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                item_state_change_event("Unittest_Sun", test_case.sun)
                item_state_change_event("Unittest_Winter", test_case.heating_active)
                item_state_change_event("Unittest_Presence_state", test_case.presence_state.value)

                assert_item_value("Unittest_Output_1", test_case.out_full)
                assert_item_value("Unittest_Output_2", test_case.out_winter)
