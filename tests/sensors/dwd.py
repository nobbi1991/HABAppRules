"""Test DWD rules."""

import collections
import datetime
import pathlib
import sys
import unittest.mock

import HABApp

import habapp_rules.sensors.config.dwd
import habapp_rules.sensors.dwd
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base


class TestDwdItems(tests.helper.test_case_base.TestCaseBase):
    """Tests for DwdItems."""

    def setUp(self) -> None:
        """Setup tests."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_1_description", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_1_type", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_1_severity", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "I26_99_warning_1_start_time", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "I26_99_warning_1_end_time", None)

        self._test_dataclass = habapp_rules.sensors.dwd.DwdItems.from_prefix("I26_99_warning_1")

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
                tests.helper.oh_item.set_state("I26_99_warning_1_severity", test_case.str_value)
                self.assertEqual(test_case.expected_int, self._test_dataclass.severity_as_int)


class TestDwdWindAlarm(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests for DwdWindAlarm."""

    def setUp(self) -> None:
        """Setup tests."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Wind_Alarm_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Wind_Alarm_1_state", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Wind_Alarm_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Wind_Alarm_2_state", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Hand_Timeout", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_1_description", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_1_type", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_1_severity", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "I26_99_warning_1_start_time", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "I26_99_warning_1_end_time", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_2_description", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_2_type", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "I26_99_warning_2_severity", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "I26_99_warning_2_start_time", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "I26_99_warning_2_end_time", None)

        config_1 = habapp_rules.sensors.config.dwd.WindAlarmConfig(
            items=habapp_rules.sensors.config.dwd.WindAlarmItems(wind_alarm="Unittest_Wind_Alarm_1", manual="Unittest_Manual_1", state="H_Unittest_Wind_Alarm_1_state"),
            parameter=habapp_rules.sensors.config.dwd.WindAlarmParameter(hand_timeout=12 * 3600, number_dwd_objects=2),
        )

        config_2 = habapp_rules.sensors.config.dwd.WindAlarmConfig(
            items=habapp_rules.sensors.config.dwd.WindAlarmItems(wind_alarm="Unittest_Wind_Alarm_2", manual="Unittest_Manual_2", hand_timeout="Unittest_Hand_Timeout", state="Unittest_Wind_Alarm_2_state"),
            parameter=habapp_rules.sensors.config.dwd.WindAlarmParameter(number_dwd_objects=2),
        )

        self._wind_alarm_rule_1 = habapp_rules.sensors.dwd.DwdWindAlarm(config_1)
        self._wind_alarm_rule_2 = habapp_rules.sensors.dwd.DwdWindAlarm(config_2)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "DWD_WindAlarm"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
            model=tests.helper.graph_machines.FakeModel(), states=self._wind_alarm_rule_1.states, transitions=self._wind_alarm_rule_1.trans, initial=self._wind_alarm_rule_1.state, show_conditions=True
        )

        graph.get_graph().draw(picture_dir / "DWD_Wind_Alarm.png", format="png", prog="dot")

    def test_set_timeouts(self) -> None:
        """Test _set_timeouts."""
        self.assertEqual(12 * 3600, self._wind_alarm_rule_1.state_machine.get_state("Hand").timeout)
        self.assertEqual(24 * 3600, self._wind_alarm_rule_2.state_machine.get_state("Hand").timeout)

        tests.helper.oh_item.item_state_change_event("Unittest_Hand_Timeout", 2000)
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
                    tests.helper.oh_item.set_state("Unittest_Manual_1", test_case.manual)
                    wind_alarm_active_mock.return_value = test_case.wind_alarm_active

                    self.assertEqual(test_case.expected_state, self._wind_alarm_rule_1._get_initial_state())

    def test_manual(self) -> None:
        """Test manual."""
        # from Auto
        self.assertEqual("Auto_Off", self._wind_alarm_rule_1.state)
        self.assertEqual("Auto_Off", self._wind_alarm_rule_2.state)

        tests.helper.oh_item.item_state_change_event("Unittest_Manual_1", "ON")
        tests.helper.oh_item.item_state_change_event("Unittest_Manual_2", "ON")
        self.assertEqual("Manual", self._wind_alarm_rule_1.state)
        self.assertEqual("Manual", self._wind_alarm_rule_2.state)

        tests.helper.oh_item.item_state_change_event("Unittest_Manual_1", "OFF")
        tests.helper.oh_item.item_state_change_event("Unittest_Manual_2", "OFF")
        self.assertEqual("Auto_Off", self._wind_alarm_rule_1.state)
        self.assertEqual("Auto_Off", self._wind_alarm_rule_2.state)

        # from Hand
        tests.helper.oh_item.item_state_change_event("Unittest_Wind_Alarm_1", "ON")
        tests.helper.oh_item.item_state_change_event("Unittest_Wind_Alarm_2", "ON")
        self.assertEqual("Hand", self._wind_alarm_rule_1.state)
        self.assertEqual("Hand", self._wind_alarm_rule_2.state)

        tests.helper.oh_item.item_state_change_event("Unittest_Manual_1", "ON")
        tests.helper.oh_item.item_state_change_event("Unittest_Manual_2", "ON")
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
                tests.helper.oh_item.set_state("I26_99_warning_1_description", test_case.description_1)
                tests.helper.oh_item.set_state("I26_99_warning_1_type", test_case.type_1)
                tests.helper.oh_item.set_state("I26_99_warning_1_severity", test_case.severity_1)
                tests.helper.oh_item.set_state("I26_99_warning_1_start_time", test_case.start_time_1)
                tests.helper.oh_item.set_state("I26_99_warning_1_end_time", test_case.end_time_1)

                tests.helper.oh_item.set_state("I26_99_warning_2_description", test_case.description_2)
                tests.helper.oh_item.set_state("I26_99_warning_2_type", test_case.type_2)
                tests.helper.oh_item.set_state("I26_99_warning_2_severity", test_case.severity_2)
                tests.helper.oh_item.set_state("I26_99_warning_2_start_time", test_case.start_time_2)
                tests.helper.oh_item.set_state("I26_99_warning_2_end_time", test_case.end_time_2)

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
                    tests.helper.oh_item.assert_value("Unittest_Wind_Alarm_1", "ON" if test_case.expected_state == "Auto_On" else "OFF")
