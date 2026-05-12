"""Test light HCL rules."""

import collections
import datetime
import sys
import unittest.mock

from HABApp.openhab.items import DimmerItem, NumberItem, StringItem, SwitchItem

from habapp_rules.actors.config.light_hcl import HclElevationConfig, HclElevationItems, HclElevationParameter, HclTimeConfig, HclTimeItems, HclTimeParameter
from habapp_rules.actors.light_hcl import HclElevation, HclTime
from habapp_rules.system import SleepState
from tests.helper.graph_machines import create_state_graphs
from tests.helper.oh_item import add_mock_item, assert_item_value, item_state_change_event, set_item_state
from tests.helper.test_case_base import TestCaseBase, TestCaseBaseStateMachine


class TestHclElevation(TestCaseBaseStateMachine):
    """Tests for elevation-based HCL."""

    def setUp(self) -> None:
        """Setup tests."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Elevation", None)

        add_mock_item(NumberItem, "Unittest_Color_min", None)
        add_mock_item(SwitchItem, "Unittest_Manual_min", None)
        add_mock_item(StringItem, "H_Unittest_Color_min_state", None)

        add_mock_item(NumberItem, "Unittest_Color_max", None)
        add_mock_item(SwitchItem, "Unittest_Manual_max", None)
        add_mock_item(StringItem, "Unittest_Sleep_state", None)
        add_mock_item(SwitchItem, "Unittest_Focus_max", None)
        add_mock_item(SwitchItem, "Unittest_Switch_on_max", None)
        add_mock_item(StringItem, "H_State_max", None)

        self._config_min = HclElevationConfig(
            items=HclElevationItems(color="Unittest_Color_min", manual="Unittest_Manual_min", elevation="Unittest_Elevation", state="H_Unittest_Color_min_state"),
            parameter=HclElevationParameter(color_map=[(-10, 3000), (-2, 3800), (0, 4200.0), (10, 5000)]),
        )

        self._config_max = HclElevationConfig(
            items=HclElevationItems(
                color="Unittest_Color_max",
                manual="Unittest_Manual_max",
                elevation="Unittest_Elevation",
                state="H_State_max",
                sleep_state="Unittest_Sleep_state",
                focus="Unittest_Focus_max",
                switch_on="Unittest_Switch_on_max",
            ),
            parameter=HclElevationParameter(color_map=[(-10, 3000), (-2, 3800), (0, 4200.0), (10, 5000)], hand_timeout=30 * 60, sleep_color=3000, post_sleep_timeout=500, focus_color=7000),
        )

        self._hcl_elevation_min = HclElevation(self._config_min)
        self._hcl_elevation_max = HclElevation(self._config_max)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        create_state_graphs(self._hcl_elevation_min, "Light_HCL")

    def test_set_timeouts(self) -> None:
        """Test _set_timeouts."""
        # min
        self.assertEqual(18000, self._hcl_elevation_min.state_machine.get_state("Hand").timeout)
        self.assertEqual(1, self._hcl_elevation_min.state_machine.get_state("Auto_Sleep_Post").timeout)

        # max
        self.assertEqual(1800, self._hcl_elevation_max.state_machine.get_state("Hand").timeout)
        self.assertEqual(500, self._hcl_elevation_max.state_machine.get_state("Auto_Sleep_Post").timeout)

    def test_get_initial_state(self) -> None:
        """Test _get_initial_state."""
        TestCase = collections.namedtuple("TestCase", "manual, focus, sleep_state, result_min, result_max")

        test_cases = [
            TestCase("OFF", "OFF", SleepState.AWAKE, "Auto_HCL", "Auto_HCL"),
            TestCase("OFF", "OFF", SleepState.PRE_SLEEPING, "Auto_HCL", "Auto_Sleep"),
            TestCase("OFF", "OFF", SleepState.SLEEPING, "Auto_HCL", "Auto_Sleep"),
            TestCase("OFF", "OFF", SleepState.POST_SLEEPING, "Auto_HCL", "Auto_HCL"),
            TestCase("OFF", "ON", SleepState.AWAKE, "Auto_HCL", "Auto_Focus"),
            TestCase("OFF", "ON", SleepState.PRE_SLEEPING, "Auto_HCL", "Auto_Sleep"),
            TestCase("OFF", "ON", SleepState.SLEEPING, "Auto_HCL", "Auto_Sleep"),
            TestCase("OFF", "ON", SleepState.POST_SLEEPING, "Auto_HCL", "Auto_Focus"),
            TestCase("ON", "OFF", SleepState.AWAKE, "Manual", "Manual"),
            TestCase("ON", "OFF", SleepState.PRE_SLEEPING, "Manual", "Manual"),
            TestCase("ON", "OFF", SleepState.SLEEPING, "Manual", "Manual"),
            TestCase("ON", "OFF", SleepState.POST_SLEEPING, "Manual", "Manual"),
            TestCase("ON", "ON", SleepState.AWAKE, "Manual", "Manual"),
            TestCase("ON", "ON", SleepState.PRE_SLEEPING, "Manual", "Manual"),
            TestCase("ON", "ON", SleepState.SLEEPING, "Manual", "Manual"),
            TestCase("ON", "ON", SleepState.POST_SLEEPING, "Manual", "Manual"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("Unittest_Manual_min", test_case.manual)
                set_item_state("Unittest_Manual_max", test_case.manual)
                set_item_state("Unittest_Focus_max", test_case.focus)
                set_item_state("Unittest_Sleep_state", test_case.sleep_state.value)

                self.assertEqual(test_case.result_min, self._hcl_elevation_min._get_initial_state())
                self.assertEqual(test_case.result_max, self._hcl_elevation_max._get_initial_state())

    def test_get_hcl_color(self) -> None:
        """Test _get_hcl_color."""
        TestCase = collections.namedtuple("TestCase", "input, output")

        test_cases = [
            TestCase(-20, 3000),
            TestCase(-10.5, 3000),
            TestCase(-10, 3000),
            TestCase(-6, 3400),
            TestCase(-2, 3800),
            TestCase(-1, 4000),
            TestCase(0, 4200),
            TestCase(5, 4600),
            TestCase(10, 5000),
            TestCase(12, 5000),
            TestCase(0.5, 4240),
            TestCase(0.2556, 4220),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._hcl_elevation_min._config.items.elevation.value = test_case.input
                self.assertEqual(test_case.output, self._hcl_elevation_min._get_hcl_color())

    def test_sleep_active(self) -> None:
        """Test _sleep_active."""
        # sleep_state is not configured
        self.assertIsNone(self._hcl_elevation_min._config.items.sleep_state)
        self.assertFalse(self._hcl_elevation_min._sleep_active())

        # sleep_state is configured
        self.assertIsNotNone(self._hcl_elevation_max._config.items.sleep_state)

        TestCase = collections.namedtuple("TestCase", "sleep_state, result")
        test_cases = [
            TestCase(SleepState.AWAKE.value, False),
            TestCase(SleepState.PRE_SLEEPING.value, True),
            TestCase(SleepState.SLEEPING.value, True),
            TestCase(SleepState.POST_SLEEPING.value, False),
            TestCase(SleepState.LOCKED.value, False),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("Unittest_Sleep_state", test_case.sleep_state)
                self.assertEqual(test_case.result, self._hcl_elevation_max._sleep_active())

    def test_end_to_end(self) -> None:
        """Test end to end behavior."""
        assert_item_value("Unittest_Color_min", 4200)
        item_state_change_event("Unittest_Elevation", 20)
        assert_item_value("Unittest_Color_min", 5000)

    def test_manual(self) -> None:
        """Test manual."""
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_HCL", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Manual_min", "ON")
        item_state_change_event("Unittest_Manual_max", "ON")
        self.assertEqual("Manual", self._hcl_elevation_min.state)
        self.assertEqual("Manual", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Manual_min", "OFF")
        item_state_change_event("Unittest_Manual_max", "OFF")
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_HCL", self._hcl_elevation_max.state)

    def test_hand(self) -> None:
        """Test hand detection."""
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_HCL", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Color_min", 42)
        item_state_change_event("Unittest_Color_max", 42)

        self.assertEqual("Hand", self._hcl_elevation_min.state)
        self.assertEqual("Hand", self._hcl_elevation_max.state)

    def test_focus(self) -> None:
        """Test focus."""
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_HCL", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Focus_max", "ON")
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_Focus", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Focus_max", "OFF")
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_HCL", self._hcl_elevation_max.state)

    def test_sleep(self) -> None:
        """Test sleep."""
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_HCL", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Sleep_state", SleepState.PRE_SLEEPING.value)
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_Sleep_Active", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Sleep_state", SleepState.SLEEPING.value)
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_Sleep_Active", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Sleep_state", SleepState.POST_SLEEPING.value)
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_Sleep_Active", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Sleep_state", SleepState.AWAKE.value)
        self.assertEqual("Auto_HCL", self._hcl_elevation_min.state)
        self.assertEqual("Auto_Sleep_Post", self._hcl_elevation_max.state)

        self._hcl_elevation_max.post_sleep_timeout()
        self.assertEqual("Auto_HCL", self._hcl_elevation_max.state)

        # with focus on
        item_state_change_event("Unittest_Focus_max", "ON")
        self.assertEqual("Auto_Focus", self._hcl_elevation_max.state)

        item_state_change_event("Unittest_Sleep_state", SleepState.PRE_SLEEPING.value)
        self.assertEqual("Auto_Sleep_Active", self._hcl_elevation_max.state)
        assert_item_value("Unittest_Focus_max", "OFF")

    def test_switch_on(self) -> None:
        """Test switch on."""
        self._hcl_elevation_max.state = "Manual"
        add_mock_item(NumberItem, "Unittest_Color_dimmer", None)
        add_mock_item(SwitchItem, "Unittest_Manual_dimmer", None)
        add_mock_item(StringItem, "Unittest_Color_dimmer_state", None)
        add_mock_item(DimmerItem, "Unittest_Switch_on_dimmer", None)

        hcl_color_dimmer = HclElevation(
            HclElevationConfig(
                items=HclElevationItems(
                    color="Unittest_Color_dimmer",
                    manual="Unittest_Manual_dimmer",
                    elevation="Unittest_Elevation",
                    state="Unittest_Color_dimmer_state",
                    switch_on="Unittest_Switch_on_dimmer",
                )
            )
        )

        # event value == OFF
        with unittest.mock.patch.object(hcl_color_dimmer, "_set_light_color") as set_color_dimmer_mock, unittest.mock.patch.object(self._hcl_elevation_max, "_set_light_color") as set_color_max_mock:
            item_state_change_event("Unittest_Switch_on_max", "OFF")
            item_state_change_event("Unittest_Switch_on_dimmer", 0)
            set_color_dimmer_mock.assert_not_called()
            set_color_max_mock.assert_not_called()

        # event value == ON
        with unittest.mock.patch.object(hcl_color_dimmer, "_set_light_color") as set_color_dimmer_mock, unittest.mock.patch.object(self._hcl_elevation_max, "_set_light_color") as set_color_max_mock:
            item_state_change_event("Unittest_Switch_on_max", "ON")
            item_state_change_event("Unittest_Switch_on_dimmer", 42)
            set_color_dimmer_mock.assert_called_once()
            set_color_max_mock.assert_called_once()


class TestHclTime(TestCaseBaseStateMachine):
    """Tests for time-based HCL."""

    def setUp(self) -> None:
        """Set up tests."""
        TestCaseBase.setUp(self)
        add_mock_item(NumberItem, "Unittest_Color_min", None)
        add_mock_item(SwitchItem, "Unittest_Manual_min", None)
        add_mock_item(StringItem, "H_Unittest_Color_min_state", None)

        self._config = HclTimeConfig(
            items=HclTimeItems(
                color=NumberItem("Unittest_Color_min"),
                manual=SwitchItem("Unittest_Manual_min"),
                state=StringItem("H_Unittest_Color_min_state"),
            ),
            parameter=HclTimeParameter(
                color_map=[(2, 3000), (8, 4000), (12, 9000), (17, 9000), (20, 4000)],
            ),
        )

        self._rule = HclTime(self._config)

    def test_one_hour_later(self) -> None:
        """Test _one_hour_later."""
        TestCase = collections.namedtuple("TestCase", "configured, time, today_weekend_holiday, tomorrow_weekend_holiday, expected_result")

        test_cases = [
            # not configured -> always false
            TestCase(False, datetime.datetime(2023, 12, 19, 12), False, False, False),
            # 12:00 -> always false
            TestCase(True, datetime.datetime(2023, 12, 19, 12), False, False, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 12), False, True, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 12), True, False, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 12), True, True, False),
            # 13:00 -> true if next day is a free day
            TestCase(True, datetime.datetime(2023, 12, 19, 13), False, False, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 13), False, True, True),
            TestCase(True, datetime.datetime(2023, 12, 19, 13), True, False, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 13), True, True, True),
            # 4:00 -> true if today is a free day
            TestCase(True, datetime.datetime(2023, 12, 19, 4), False, False, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 4), False, True, True),
            TestCase(True, datetime.datetime(2023, 12, 19, 4), True, False, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 4), True, True, True),
            # 5:00 -> always false
            TestCase(True, datetime.datetime(2023, 12, 19, 5), False, False, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 5), False, True, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 5), True, False, False),
            TestCase(True, datetime.datetime(2023, 12, 19, 5), True, True, False),
        ]

        with unittest.mock.patch("habapp_rules.actors.light_hcl.is_holiday") as is_holiday_mock, unittest.mock.patch("habapp_rules.actors.light_hcl.is_weekend") as is_weekend_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    # test holiday
                    is_holiday_mock.side_effect = [test_case.tomorrow_weekend_holiday, test_case.today_weekend_holiday]
                    is_weekend_mock.side_effect = [False, False]
                    self._rule._config.parameter.shift_weekend_holiday = test_case.configured

                    self.assertEqual(test_case.expected_result, self._rule._one_hour_later(test_case.time))

                    # test weekend
                    is_holiday_mock.side_effect = [False, False]
                    is_weekend_mock.side_effect = [test_case.tomorrow_weekend_holiday, test_case.today_weekend_holiday]
                    self._rule._config.parameter.shift_weekend_holiday = test_case.configured

                    self.assertEqual(test_case.expected_result, self._rule._one_hour_later(test_case.time))

    def test_get_hcl_color(self) -> None:
        """Test _get_hcl_color."""
        # test without color value as attribute
        TestCase = collections.namedtuple("TestCase", "test_time, output")

        test_cases = [
            TestCase(datetime.datetime(2023, 1, 1, 0, 0), 3333),
            TestCase(datetime.datetime(2023, 1, 1, 1, 0), 3167),
            TestCase(datetime.datetime(2023, 1, 1, 2, 0), 3000),
            TestCase(datetime.datetime(2023, 1, 1, 3, 30), 3250),
            TestCase(datetime.datetime(2023, 1, 1, 5, 0), 3500),
            TestCase(datetime.datetime(2023, 1, 1, 8, 0), 4000),
            TestCase(datetime.datetime(2023, 1, 1, 9, 0), 5250),
            TestCase(datetime.datetime(2023, 1, 1, 12, 0), 9000),
            TestCase(datetime.datetime(2023, 1, 1, 12, 10), 9000),
            TestCase(datetime.datetime(2023, 1, 1, 20, 0), 4000),
            TestCase(datetime.datetime(2023, 1, 1, 22, 0), 3667),
            TestCase(datetime.datetime(2023, 1, 1, 22, 12), 3633),
        ]

        with unittest.mock.patch("datetime.datetime") as datetime_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    datetime_mock.now.return_value = test_case.test_time
                    self.assertEqual(test_case.output, round(self._rule._get_hcl_color()))

        # test one hour later
        test_time = datetime.datetime(2023, 1, 1, 21, 0)
        with unittest.mock.patch.object(self._rule, "_one_hour_later", return_value=True), unittest.mock.patch("datetime.datetime") as datetime_mock:
            datetime_mock.now.return_value = test_time
            self.assertEqual(4000, round(self._rule._get_hcl_color()))

    def test_update_color(self) -> None:
        """Test _update_color."""
        with unittest.mock.patch.object(self._rule, "_get_hcl_color", return_value=42):
            self._rule._update_color()
        assert_item_value("Unittest_Color_min", 42)

        # state is not Auto_HCL:
        item_state_change_event("Unittest_Manual_min", "ON")
        with unittest.mock.patch.object(self._rule, "_get_hcl_color", return_value=123):
            self._rule._update_color()
        assert_item_value("Unittest_Color_min", 42)
