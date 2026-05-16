"""Test DWD rules."""

import collections
import datetime
import sys
import unittest.mock

from HABApp.openhab.items import DatetimeItem, NumberItem, StringItem, SwitchItem

from habapp_rules.sensors.config.dwd import WindAlarmConfig, WindAlarmItems, WindAlarmParameter
from habapp_rules.sensors.dwd import DwdItems, DwdWindAlarm
from tests.helper.graph_machines import create_state_graphs
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_change_event,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBase, TestCaseBaseStateMachine


class TestDwdItems(TestCaseBase):
    """Tests for DwdItems."""

    def setUp(self) -> None:
        """Setup tests."""
        TestCaseBase.setUp(self)

        add_mock_item(StringItem, "I26_99_warning_1_description", None)
        add_mock_item(StringItem, "I26_99_warning_1_type", None)
        add_mock_item(StringItem, "I26_99_warning_1_severity", None)
        add_mock_item(DatetimeItem, "I26_99_warning_1_start_time", None)
        add_mock_item(DatetimeItem, "I26_99_warning_1_end_time", None)

        self._test_dataclass = DwdItems.from_prefix("I26_99_warning_1")

    def test_severity_as_int(self) -> None:
        """Test severity_as_int."""
        TestCase = collections.namedtuple("TestCase", "str_value, expected_int")

        test_cases = [
            TestCase("NULL", 0),
            TestCase("Minor", 1),
            TestCase("Moderate", 2),
            TestCase("Severe", 3),
            TestCase("Extreme", 4),
            TestCase("UNKNOWN", 0),
            TestCase(None, 0),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("I26_99_warning_1_severity", test_case.str_value)
                self.assertEqual(test_case.expected_int, self._test_dataclass.severity_as_int)


class TestDwdWindAlarm(TestCaseBaseStateMachine):
    """Tests for DwdWindAlarm."""

    def setUp(self) -> None:
        """Setup tests."""
        super().setUp()

        add_mock_item(SwitchItem, "Unittest_Wind_Alarm_1", None)
        add_mock_item(SwitchItem, "Unittest_Manual_1", None)
        add_mock_item(StringItem, "H_Unittest_Wind_Alarm_1_state", None)

        add_mock_item(SwitchItem, "Unittest_Wind_Alarm_2", None)
        add_mock_item(SwitchItem, "Unittest_Manual_2", None)
        add_mock_item(StringItem, "Unittest_Wind_Alarm_2_state", None)
        add_mock_item(NumberItem, "Unittest_Hand_Timeout", None)

        add_mock_item(StringItem, "I26_99_warning_1_description", None)
        add_mock_item(StringItem, "I26_99_warning_1_type", None)
        add_mock_item(StringItem, "I26_99_warning_1_severity", None)
        add_mock_item(DatetimeItem, "I26_99_warning_1_start_time", None)
        add_mock_item(DatetimeItem, "I26_99_warning_1_end_time", None)

        add_mock_item(StringItem, "I26_99_warning_2_description", None)
        add_mock_item(StringItem, "I26_99_warning_2_type", None)
        add_mock_item(StringItem, "I26_99_warning_2_severity", None)
        add_mock_item(DatetimeItem, "I26_99_warning_2_start_time", None)
        add_mock_item(DatetimeItem, "I26_99_warning_2_end_time", None)

        config_1 = WindAlarmConfig(
            items=WindAlarmItems(wind_alarm="Unittest_Wind_Alarm_1", manual="Unittest_Manual_1", state="H_Unittest_Wind_Alarm_1_state"),
            parameter=WindAlarmParameter(hand_timeout=12 * 3600, number_dwd_objects=2),
        )

        config_2 = WindAlarmConfig(
            items=WindAlarmItems(wind_alarm="Unittest_Wind_Alarm_2", manual="Unittest_Manual_2", hand_timeout="Unittest_Hand_Timeout", state="Unittest_Wind_Alarm_2_state"),
            parameter=WindAlarmParameter(number_dwd_objects=2),
        )

        self._wind_alarm_rule_1 = DwdWindAlarm(config_1)
        self._wind_alarm_rule_2 = DwdWindAlarm(config_2)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        create_state_graphs(self._wind_alarm_rule_1, "DWD_WindAlarm")

    def test_set_timeouts(self) -> None:
        """Test _set_timeouts."""
        self.assertEqual(12 * 3600, self._wind_alarm_rule_1.state_machine.get_state("Hand").timeout)
        self.assertEqual(24 * 3600, self._wind_alarm_rule_2.state_machine.get_state("Hand").timeout)

        item_state_change_event("Unittest_Hand_Timeout", 2000)
        self.assertEqual(2000, self._wind_alarm_rule_2.state_machine.get_state("Hand").timeout)

    def test_get_initial_state(self) -> None:
        """Test _get_initial_state."""
        TestCase = collections.namedtuple("TestCase", "manual, wind_alarm_active, expected_state")

        test_cases = [
            TestCase("OFF", False, "Auto_Off"),
            TestCase("OFF", True, "Auto_On"),
            TestCase("ON", False, "Manual"),
            TestCase("ON", True, "Manual"),
        ]

        with unittest.mock.patch.object(self._wind_alarm_rule_1, "_wind_alarm_active") as wind_alarm_active_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    set_item_state("Unittest_Manual_1", test_case.manual)
                    wind_alarm_active_mock.return_value = test_case.wind_alarm_active

                    self.assertEqual(test_case.expected_state, self._wind_alarm_rule_1._get_initial_state())

    def test_manual(self) -> None:
        """Test manual."""
        # from Auto
        self.assertEqual("Auto_Off", self._wind_alarm_rule_1.state)
        self.assertEqual("Auto_Off", self._wind_alarm_rule_2.state)

        item_state_change_event("Unittest_Manual_1", "ON")
        item_state_change_event("Unittest_Manual_2", "ON")
        self.assertEqual("Manual", self._wind_alarm_rule_1.state)
        self.assertEqual("Manual", self._wind_alarm_rule_2.state)

        item_state_change_event("Unittest_Manual_1", "OFF")
        item_state_change_event("Unittest_Manual_2", "OFF")
        self.assertEqual("Auto_Off", self._wind_alarm_rule_1.state)
        self.assertEqual("Auto_Off", self._wind_alarm_rule_2.state)

        # from Hand
        item_state_change_event("Unittest_Wind_Alarm_1", "ON")
        item_state_change_event("Unittest_Wind_Alarm_2", "ON")
        self.assertEqual("Hand", self._wind_alarm_rule_1.state)
        self.assertEqual("Hand", self._wind_alarm_rule_2.state)

        item_state_change_event("Unittest_Manual_1", "ON")
        item_state_change_event("Unittest_Manual_2", "ON")
        self.assertEqual("Manual", self._wind_alarm_rule_1.state)
        self.assertEqual("Manual", self._wind_alarm_rule_2.state)

    def test_wind_alarm_active(self) -> None:
        """Test _wind_alarm_active."""
        TestCase = collections.namedtuple("TestCase", "type_1, description_1, severity_1 start_time_1, end_time_1, type_2, description_2, severity_2 start_time_2, end_time_2, expected_result")

        now = datetime.datetime.now()
        start_active = now + datetime.timedelta(hours=-1)
        end_active = now + datetime.timedelta(hours=1)
        start_not_active = now + datetime.timedelta(hours=1)
        end_not_active = now + datetime.timedelta(hours=-2)

        test_cases = [
            TestCase(None, None, None, None, None, None, None, None, None, None, False),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "SUN", "SUN is appearing at 100 km/h", "Minor", start_not_active, end_not_active, False),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "SUN", "SUN is appearing at 100 km/h", "Minor", start_active, end_active, False),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "SUN", "SUN is appearing at 100 km/h", "Moderate", start_active, end_active, False),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "SUN", "Wind speed above 100 km/h", "Moderate", start_active, end_active, False),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "WIND", "Wind speed above 100 km/h", "Moderate", start_active, end_active, True),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "WIND", "Wind speed very high", "Moderate", start_active, end_active, False),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "WIND", "Wind speed above 100 km/h", "Minor", start_active, end_active, False),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "WIND", "Wind speed above 10 km/h", "Extreme", start_active, end_active, False),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "WIND", "Wind speed between 5 km/h and 100 km/h", "Moderate", start_active, end_active, True),
            TestCase("FROST", "Frost is appearing at 100 km/h", "Minor", start_not_active, end_not_active, "WIND", "Wind speed between 5 km/h and 100 km/h", "Moderate", start_not_active, end_not_active, False),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("I26_99_warning_1_description", test_case.description_1)
                set_item_state("I26_99_warning_1_type", test_case.type_1)
                set_item_state("I26_99_warning_1_severity", test_case.severity_1)
                set_item_state("I26_99_warning_1_start_time", test_case.start_time_1)
                set_item_state("I26_99_warning_1_end_time", test_case.end_time_1)

                set_item_state("I26_99_warning_2_description", test_case.description_2)
                set_item_state("I26_99_warning_2_type", test_case.type_2)
                set_item_state("I26_99_warning_2_severity", test_case.severity_2)
                set_item_state("I26_99_warning_2_start_time", test_case.start_time_2)
                set_item_state("I26_99_warning_2_end_time", test_case.end_time_2)

                self.assertEqual(test_case.expected_result, self._wind_alarm_rule_1._wind_alarm_active())

    def test_cyclic_check(self) -> None:
        """Test _cyclic_check."""
        # Manual / Hand should not trigger any test
        with unittest.mock.patch.object(self._wind_alarm_rule_1, "_wind_alarm_active") as check_wind_alarm_mock:
            for state in ("Manual", "Hand"):
                self._wind_alarm_rule_1.state = state
                self._wind_alarm_rule_1._cb_cyclic_check()
        check_wind_alarm_mock.assert_not_called()

        # Auto will trigger check and send if needed
        TestCase = collections.namedtuple("TestCase", "initial_state, wind_alarm_active, expected_state")

        test_cases = [
            TestCase("Auto_Off", False, "Auto_Off"),
            TestCase("Auto_Off", True, "Auto_On"),
            TestCase("Auto_On", True, "Auto_On"),
            TestCase("Auto_On", False, "Auto_Off"),
        ]

        with unittest.mock.patch.object(self._wind_alarm_rule_1, "_wind_alarm_active") as check_wind_alarm_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    self._wind_alarm_rule_1.state = test_case.initial_state
                    check_wind_alarm_mock.return_value = test_case.wind_alarm_active

                    self._wind_alarm_rule_1._cb_cyclic_check()

                    self.assertEqual(test_case.expected_state, self._wind_alarm_rule_1.state)
                    assert_item_value("Unittest_Wind_Alarm_1", "ON" if test_case.expected_state == "Auto_On" else "OFF")
