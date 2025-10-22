"""Tests for sun sensors."""

import collections
import unittest.mock

import HABApp

import habapp_rules.sensors.config.sun
import habapp_rules.sensors.sun
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.system import PresenceState


class TestSensorTemperatureDifference(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing sun sensor 'temp_diff' rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_Temperature", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Threshold_Temperature", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "H_Temperature_diff_for_Unittest_Output_Temperature", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "H_Temperature_diff_for_Unittest_Output_Temperature_filtered", None)

        config = habapp_rules.sensors.config.sun.TemperatureDifferenceConfig(
            items=habapp_rules.sensors.config.sun.TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1", "Unittest_Temperature_2"], output="Unittest_Output_Temperature", threshold="Unittest_Threshold_Temperature")
        )

        with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True), unittest.mock.patch("habapp_rules.common.filter.ExponentialFilter"):
            self._sensor = habapp_rules.sensors.sun.SensorTemperatureDifference(config)

    def test_init(self) -> None:
        """Test __init__."""
        self.assertEqual(float("inf"), self._sensor._hysteresis_switch._threshold)
        self.assertEqual("H_Temperature_diff_for_Unittest_Output_Temperature", self._sensor._item_temp_diff.name)

    def test_init_with_fixed_threshold(self) -> None:
        """Test __init__ with fixed threshold value."""
        config = habapp_rules.sensors.config.sun.TemperatureDifferenceConfig(
            items=habapp_rules.sensors.config.sun.TemperatureDifferenceItems(temperatures=["Unittest_Temperature_1", "Unittest_Temperature_2"], output="Unittest_Output_Temperature"),
            parameter=habapp_rules.sensors.config.sun.TemperatureDifferenceParameter(threshold=42),
        )

        with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True), unittest.mock.patch("habapp_rules.common.filter.ExponentialFilter"):
            sensor = habapp_rules.sensors.sun.SensorTemperatureDifference(config)
        self.assertEqual(42, sensor._hysteresis_switch._threshold)

    def test_cb_threshold(self) -> None:
        """Test _cb_threshold."""
        tests.helper.oh_item.item_state_change_event("Unittest_Threshold_Temperature", 20)
        self.assertEqual(20, self._sensor._hysteresis_switch._threshold)

    def test_temp_diff(self) -> None:
        """Test if temperature difference is calculated correctly."""
        temp_diff_item = HABApp.openhab.items.OpenhabItem.get_item("H_Temperature_diff_for_Unittest_Output_Temperature")
        self.assertEqual(None, temp_diff_item.value)

        # update temperature 1
        tests.helper.oh_item.item_state_change_event("Unittest_Temperature_1", 20)
        self.assertEqual(None, temp_diff_item.value)

        # update temperature 2
        tests.helper.oh_item.item_state_change_event("Unittest_Temperature_2", 21)
        self.assertEqual(1, temp_diff_item.value)

        # update temperature 2
        tests.helper.oh_item.item_state_change_event("Unittest_Temperature_2", 18)
        self.assertEqual(2, temp_diff_item.value)

        # update temperature 1
        tests.helper.oh_item.item_state_change_event("Unittest_Temperature_1", -20)
        self.assertEqual(38, temp_diff_item.value)

        # update temperature 2
        tests.helper.oh_item.item_state_change_event("Unittest_Temperature_2", -25)
        self.assertEqual(5, temp_diff_item.value)

    def test_threshold_behavior(self) -> None:
        """Test overall behavior."""
        output_item = HABApp.openhab.items.OpenhabItem.get_item("Unittest_Output_Temperature")
        self.assertEqual(None, output_item.value)

        # set threshold to 10
        self._sensor._hysteresis_switch.set_threshold_on(10)

        # update temp_diff to 10
        tests.helper.oh_item.item_state_change_event("H_Temperature_diff_for_Unittest_Output_Temperature_filtered", 10)
        self.assertEqual("ON", output_item.value)

        # update temp_diff to 9.9
        tests.helper.oh_item.item_state_change_event("H_Temperature_diff_for_Unittest_Output_Temperature_filtered", 9.9)
        self.assertEqual("OFF", output_item.value)

        # update temp_diff to 8
        tests.helper.oh_item.item_state_change_event("H_Temperature_diff_for_Unittest_Output_Temperature_filtered", 8)
        self.assertEqual("OFF", output_item.value)


class TestSensorBrightness(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing sun sensor 'brightness' rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_Brightness", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Threshold_Brightness", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "H_Unittest_Brightness_filtered", None)

        config = habapp_rules.sensors.config.sun.BrightnessConfig(items=habapp_rules.sensors.config.sun.BrightnessItems(brightness="Unittest_Brightness", output="Unittest_Output_Brightness", threshold="Unittest_Threshold_Brightness"))

        with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True), unittest.mock.patch("habapp_rules.common.filter.ExponentialFilter"):
            self._sensor = habapp_rules.sensors.sun.SensorBrightness(config)

    def test_init(self) -> None:
        """Test __init__."""
        self.assertEqual(float("inf"), self._sensor._hysteresis_switch._threshold)

    def test_init_with_fixed_threshold(self) -> None:
        """Test __init__ with fixed threshold value."""
        config = habapp_rules.sensors.config.sun.BrightnessConfig(
            items=habapp_rules.sensors.config.sun.BrightnessItems(
                brightness="Unittest_Brightness",
                output="Unittest_Output_Brightness",
            ),
            parameter=habapp_rules.sensors.config.sun.BrightnessParameter(threshold=42),
        )

        with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True), unittest.mock.patch("habapp_rules.common.filter.ExponentialFilter"):
            sensor = habapp_rules.sensors.sun.SensorBrightness(config)
        self.assertEqual(42, sensor._hysteresis_switch._threshold)

    def test_cb_threshold(self) -> None:
        """Test _cb_threshold."""
        tests.helper.oh_item.item_state_change_event("Unittest_Threshold_Brightness", 42000)
        self.assertEqual(42000, self._sensor._hysteresis_switch._threshold)

    def test_threshold_behavior(self) -> None:
        """Test overall behavior."""
        output_item = HABApp.openhab.items.OpenhabItem.get_item("Unittest_Output_Brightness")
        self.assertEqual(None, output_item.value)

        # set threshold to 1000
        self._sensor._hysteresis_switch.set_threshold_on(1000)

        # update temp_diff to 1000
        tests.helper.oh_item.item_state_change_event("H_Unittest_Brightness_filtered", 1000)
        self.assertEqual("ON", output_item.value)

        # update temp_diff to 999
        tests.helper.oh_item.item_state_change_event("H_Unittest_Brightness_filtered", 999)
        self.assertEqual("OFF", output_item.value)

        # update temp_diff to 800
        tests.helper.oh_item.item_state_change_event("H_Unittest_Brightness_filtered", 800)
        self.assertEqual("OFF", output_item.value)


class TestSunPositionFilter(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing the sun position filter."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Input_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_1", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Input_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_2", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Azimuth", 1000)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Elevation", 1000)

        self.position_window_1 = habapp_rules.sensors.config.sun.SunPositionWindow(10, 80, 2, 20)
        self.position_window_2 = habapp_rules.sensors.config.sun.SunPositionWindow(100, 120)

        config_1 = habapp_rules.sensors.config.sun.SunPositionConfig(
            items=habapp_rules.sensors.config.sun.SunPositionItems(
                azimuth="Unittest_Azimuth",
                elevation="Unittest_Elevation",
                input="Unittest_Input_1",
                output="Unittest_Output_1",
            ),
            parameter=habapp_rules.sensors.config.sun.SunPositionParameter(sun_position_window=self.position_window_1),
        )
        config_2 = habapp_rules.sensors.config.sun.SunPositionConfig(
            items=habapp_rules.sensors.config.sun.SunPositionItems(
                azimuth="Unittest_Azimuth",
                elevation="Unittest_Elevation",
                input="Unittest_Input_2",
                output="Unittest_Output_2",
            ),
            parameter=habapp_rules.sensors.config.sun.SunPositionParameter(sun_position_window=[self.position_window_1, self.position_window_2]),
        )

        self._filter_1 = habapp_rules.sensors.sun.SunPositionFilter(config_1)
        self._filter_2 = habapp_rules.sensors.sun.SunPositionFilter(config_2)

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

        item_output_1 = HABApp.openhab.items.OpenhabItem.get_item("Unittest_Output_1")
        item_output_2 = HABApp.openhab.items.OpenhabItem.get_item("Unittest_Output_2")

        with unittest.mock.patch.object(self._filter_1, "_instance_logger") as log_1_mock, unittest.mock.patch.object(self._filter_2, "_instance_logger") as log_2_mock:
            for test_case in test_cases:
                log_1_mock.reset_mock()
                log_2_mock.reset_mock()

                tests.helper.oh_item.set_state("Unittest_Input_1", test_case.input)
                tests.helper.oh_item.set_state("Unittest_Input_2", test_case.input)

                tests.helper.oh_item.item_state_change_event("Unittest_Elevation", test_case.elevation)
                tests.helper.oh_item.item_state_change_event("Unittest_Azimuth", test_case.azimuth)

                self.assertEqual(test_case.output_1, item_output_1.value)
                self.assertEqual(test_case.output_2, item_output_2.value)

                if test_case.azimuth is None or test_case.elevation is None:
                    log_1_mock.warning.assert_called_once()
                    log_2_mock.warning.assert_called_once()
                else:
                    log_1_mock.warning.assert_not_called()
                    log_2_mock.warning.assert_not_called()


class TestWinterFilter(tests.helper.test_case_base.TestCaseBase):
    """Tests cases WinterFilter rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sun", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Winter", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_2", None)

        config_full = habapp_rules.sensors.config.sun.WinterFilterConfig(
            items=habapp_rules.sensors.config.sun.WinterFilterItems(
                sun="Unittest_Sun",
                heating_active="Unittest_Winter",
                presence_state="Unittest_Presence_state",
                output="Unittest_Output_1",
            )
        )

        config_only_heating = habapp_rules.sensors.config.sun.WinterFilterConfig(
            items=habapp_rules.sensors.config.sun.WinterFilterItems(
                sun="Unittest_Sun",
                heating_active="Unittest_Winter",
                output="Unittest_Output_2",
            )
        )

        self._rule_full = habapp_rules.sensors.sun.WinterFilter(config_full)
        self._rule_winter = habapp_rules.sensors.sun.WinterFilter(config_only_heating)

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
                tests.helper.oh_item.item_state_change_event("Unittest_Sun", test_case.sun)
                tests.helper.oh_item.item_state_change_event("Unittest_Winter", test_case.heating_active)
                tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", test_case.presence_state.value)

                tests.helper.oh_item.assert_value("Unittest_Output_1", test_case.out_full)
                tests.helper.oh_item.assert_value("Unittest_Output_2", test_case.out_winter)
