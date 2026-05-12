"""Test sleep rule."""

import collections
import datetime
import sys
import unittest
import unittest.mock

from HABApp.openhab.items import StringItem, SwitchItem

from habapp_rules.system import SleepState
from habapp_rules.system.config.sleep import LinkSleepConfig, LinkSleepItems, LinkSleepParameter, SleepConfig, SleepItems
from habapp_rules.system.sleep import LinkSleep, Sleep
from tests.helper.graph_machines import create_state_graphs
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_change_event,
    remove_mocked_item_by_name,
    send_command,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBase, TestCaseBaseStateMachine
from tests.helper.timer import call_timeout


class TestSleep(TestCaseBaseStateMachine):
    """Tests cases for testing presence rule."""

    def setUp(self) -> None:
        """Setup test case."""
        super().setUp()

        add_mock_item(SwitchItem, "Unittest_Sleep", "OFF")
        add_mock_item(SwitchItem, "Unittest_Sleep_Request", "OFF")
        add_mock_item(SwitchItem, "Unittest_Lock", "OFF")
        add_mock_item(SwitchItem, "Unittest_Lock_Request", "OFF")
        add_mock_item(StringItem, "Unittest_Display_Text", "")
        add_mock_item(StringItem, "H_Sleep_Unittest_Sleep_state", "")
        add_mock_item(StringItem, "CustomState", "")

        config = SleepConfig(items=SleepItems(sleep="Unittest_Sleep", sleep_request="Unittest_Sleep_Request", lock="Unittest_Lock", lock_request="Unittest_Lock_Request", display_text="Unittest_Display_Text", state="CustomState"))

        self._sleep = Sleep(config)

    def test_init_with_none(self) -> None:
        """Test __init__ with None values."""
        set_item_state("Unittest_Sleep", None)
        set_item_state("Unittest_Sleep_Request", None)
        set_item_state("Unittest_Lock", None)
        set_item_state("Unittest_Lock_Request", None)
        set_item_state("Unittest_Display_Text", None)
        set_item_state("CustomState", None)

        config = SleepConfig(items=SleepItems(sleep="Unittest_Sleep", sleep_request="Unittest_Sleep_Request", lock="Unittest_Lock", lock_request="Unittest_Lock_Request", display_text="Unittest_Display_Text", state="CustomState"))

        Sleep(config)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        create_state_graphs(self._sleep, "Sleep")

    def test_enums(self) -> None:
        """Test if all enums from __init__.py are implemented."""
        implemented_states = list(self._sleep.state_machine.states)
        enum_states = [state.value for state in SleepState]
        self.assertEqual(len(enum_states), len(implemented_states))
        self.assertTrue(all(state in enum_states for state in implemented_states))

    def test__init__(self) -> None:
        """Test init of sleep class."""
        TestCase = collections.namedtuple("TestCase", "sleep_request_state, lock_request_state, lock_state")

        test_cases = [
            TestCase("OFF", "OFF", "OFF"),
            TestCase("OFF", "ON", "ON"),
            TestCase("ON", "OFF", "OFF"),
            TestCase("ON", "ON", "OFF"),
        ]

        config = SleepConfig(items=SleepItems(sleep="Unittest_Sleep", sleep_request="Unittest_Sleep_Request", lock="Unittest_Lock", lock_request="Unittest_Lock_Request", display_text="Unittest_Display_Text", state="CustomState"))

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("Unittest_Sleep_Request", test_case.sleep_request_state)
                set_item_state("Unittest_Lock_Request", test_case.lock_request_state)

                sleep = Sleep(config)

                self.assertEqual(sleep.sleep_request_active, test_case.sleep_request_state == "ON", test_case)
                self.assertEqual(sleep.lock_request_active, test_case.lock_request_state == "ON", test_case)
                assert_item_value("Unittest_Sleep", test_case.sleep_request_state)
                assert_item_value("Unittest_Lock", test_case.lock_state)

    def test_get_initial_state(self) -> None:
        """Test getting initial state."""
        TestCase = collections.namedtuple("TestCase", "sleep_request, lock_request, expected_state")

        test_cases = [
            TestCase(sleep_request="OFF", lock_request="OFF", expected_state="Awake"),
            TestCase(sleep_request="OFF", lock_request="ON", expected_state="Locked"),
            TestCase(sleep_request="ON", lock_request="OFF", expected_state="Sleeping"),
            TestCase(sleep_request="ON", lock_request="ON", expected_state="Sleeping"),
            TestCase(sleep_request=None, lock_request="ON", expected_state="Locked"),
            TestCase(sleep_request=None, lock_request="OFF", expected_state="default"),
            TestCase(sleep_request="ON", lock_request=None, expected_state="Sleeping"),
            TestCase(sleep_request="OFF", lock_request=None, expected_state="Awake"),
            TestCase(sleep_request=None, lock_request=None, expected_state="default"),
        ]

        for test_case in test_cases:
            set_item_state("Unittest_Sleep_Request", test_case.sleep_request)
            set_item_state("Unittest_Lock_Request", test_case.lock_request)

            self.assertEqual(self._sleep._get_initial_state("default"), test_case.expected_state, test_case)

    def test__get_display_text(self) -> None:
        """Test getting display text."""
        TestCase = collections.namedtuple("TestCase", "state, text")
        test_cases = [TestCase("Awake", "Schlafen"), TestCase("PreSleeping", "Guten Schlaf"), TestCase("Sleeping", "Aufstehen"), TestCase("PostSleeping", "Guten Morgen"), TestCase("Locked", "Gesperrt"), TestCase(None, "")]

        for test_case in test_cases:
            self._sleep.state = test_case.state
            self.assertEqual(test_case.text, self._sleep._Sleep__get_display_text())

    def test_normal_cycle_all_items(self) -> None:
        """Test normal behavior with all items available."""
        # check initial state
        assert_item_value("CustomState", "Awake")

        # start Sleeping
        send_command("Unittest_Sleep_Request", "ON", "OFF")
        self.assertEqual(self._sleep.state, "PreSleeping")
        assert_item_value("CustomState", "PreSleeping")
        assert_item_value("Unittest_Sleep", "ON")
        assert_item_value("Unittest_Lock", "ON")
        assert_item_value("Unittest_Display_Text", "Guten Schlaf")
        self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

        # PreSleeping timeout -> sleep
        call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._sleep.state, "Sleeping")
        assert_item_value("CustomState", "Sleeping")
        assert_item_value("Unittest_Sleep", "ON")
        assert_item_value("Unittest_Lock", "OFF")
        assert_item_value("Unittest_Display_Text", "Aufstehen")

        # stop Sleeping
        self.transitions_timer_mock.reset_mock()
        send_command("Unittest_Sleep_Request", "OFF", "ON")
        self.assertEqual(self._sleep.state, "PostSleeping")
        assert_item_value("CustomState", "PostSleeping")
        assert_item_value("Unittest_Sleep", "OFF")
        assert_item_value("Unittest_Lock", "ON")
        assert_item_value("Unittest_Display_Text", "Guten Morgen")
        self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

        # PostSleeping timeout -> Awake
        call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._sleep.state, "Awake")
        assert_item_value("CustomState", "Awake")
        assert_item_value("Unittest_Sleep", "OFF")
        assert_item_value("Unittest_Lock", "OFF")
        assert_item_value("Unittest_Display_Text", "Schlafen")

    def test_lock_transitions(self) -> None:
        """Test all transitions from and to Locked state."""
        # check correct initial state
        assert_item_value("CustomState", "Awake")
        assert_item_value("Unittest_Lock", "OFF")

        # set lock_request. expected: Locked state, lock active, sleep off
        send_command("Unittest_Lock_Request", "ON", "OFF")
        assert_item_value("Unittest_Lock", "ON")
        assert_item_value("CustomState", "Locked")
        assert_item_value("Unittest_Sleep", "OFF")

        # release lock and come back to Awake state
        send_command("Unittest_Lock_Request", "OFF", "ON")
        assert_item_value("Unittest_Lock", "OFF")
        assert_item_value("CustomState", "Awake")
        assert_item_value("Unittest_Sleep", "OFF")

        # set lock_request and shortly after send sleep request -> Locked expected
        send_command("Unittest_Lock_Request", "ON", "OFF")
        send_command("Unittest_Sleep_Request", "ON", "OFF")
        assert_item_value("Unittest_Sleep_Request", "OFF")
        assert_item_value("Unittest_Lock", "ON")
        assert_item_value("CustomState", "Locked")
        assert_item_value("Unittest_Sleep", "OFF")

        # release lock and jump back to Awake
        send_command("Unittest_Lock_Request", "OFF", "ON")
        assert_item_value("Unittest_Lock", "OFF")
        assert_item_value("CustomState", "Awake")
        assert_item_value("Unittest_Sleep", "OFF")

        # start Sleeping
        send_command("Unittest_Sleep_Request", "ON", "OFF")
        assert_item_value("CustomState", "PreSleeping")

        # activate lock, remove sleep request and wait all timer -> expected state == Locked
        send_command("Unittest_Lock_Request", "ON", "OFF")
        assert_item_value("CustomState", "PreSleeping")
        call_timeout(self.transitions_timer_mock)
        assert_item_value("CustomState", "Sleeping")
        send_command("Unittest_Sleep_Request", "OFF", "ON")
        assert_item_value("CustomState", "PostSleeping")
        call_timeout(self.transitions_timer_mock)
        assert_item_value("CustomState", "Locked")

        # go back to PreSleeping and check lock + end sleep in PreSleeping -> expected state = Locked
        send_command("Unittest_Sleep_Request", "ON", "OFF")
        assert_item_value("CustomState", "Locked")
        send_command("Unittest_Lock_Request", "OFF", "ON")
        assert_item_value("CustomState", "Awake")
        send_command("Unittest_Lock_Request", "ON", "OFF")
        assert_item_value("CustomState", "Locked")

    def test_request_changed(self) -> None:
        """Test transitions when sleep request is changed at PreSleeping or PostSleeping state."""
        set_item_state("Unittest_Sleep_Request", "ON")
        self._sleep.to_PreSleeping()
        send_command("Unittest_Sleep_Request", "OFF")
        assert_item_value("CustomState", "Awake")

        set_item_state("Unittest_Sleep_Request", "OFF")
        self._sleep.to_PostSleeping()
        send_command("Unittest_Sleep_Request", "ON")
        assert_item_value("CustomState", "PreSleeping")

    def test_minimal_items(self) -> None:
        """Test Sleeping class with minimal set of items."""
        # delete sleep rule from init
        self.unload_rule(self._runner.loaded_rules[0])

        remove_mocked_item_by_name("Unittest_Lock")
        remove_mocked_item_by_name("Unittest_Lock_Request")
        remove_mocked_item_by_name("Unittest_Display_Text")

        config = SleepConfig(
            items=SleepItems(
                sleep="Unittest_Sleep",
                sleep_request="Unittest_Sleep_Request",
                state="H_Sleep_Unittest_Sleep_state",
            )
        )

        sleep = Sleep(config)

        self.assertIsNone(sleep._config.items.display_text)
        self.assertIsNone(sleep._config.items.lock)
        self.assertIsNone(sleep._config.items.lock_request)

        # check initial state
        assert_item_value("CustomState", "Awake")

        # start Sleeping
        send_command("Unittest_Sleep_Request", "ON", "OFF")
        self.assertEqual(sleep.state, "PreSleeping")
        assert_item_value("H_Sleep_Unittest_Sleep_state", "PreSleeping")
        assert_item_value("Unittest_Sleep", "ON")
        self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

        # PreSleeping timeout -> sleep
        call_timeout(self.transitions_timer_mock)
        self.assertEqual(sleep.state, "Sleeping")
        assert_item_value("H_Sleep_Unittest_Sleep_state", "Sleeping")
        assert_item_value("Unittest_Sleep", "ON")

        # stop Sleeping
        self.transitions_timer_mock.reset_mock()
        send_command("Unittest_Sleep_Request", "OFF", "ON")
        self.assertEqual(sleep.state, "PostSleeping")
        assert_item_value("H_Sleep_Unittest_Sleep_state", "PostSleeping")
        assert_item_value("Unittest_Sleep", "OFF")
        self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

        # PostSleeping timeout -> Awake
        call_timeout(self.transitions_timer_mock)
        self.assertEqual(sleep.state, "Awake")
        assert_item_value("H_Sleep_Unittest_Sleep_state", "Awake")
        assert_item_value("Unittest_Sleep", "OFF")


class TestLinkSleep(TestCaseBase):
    """Test LinkSleep."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(SwitchItem, "Unittest_Sleep1", None)
        add_mock_item(SwitchItem, "Unittest_Sleep2_req", None)
        add_mock_item(SwitchItem, "Unittest_Sleep3_req", None)

        add_mock_item(SwitchItem, "Unittest_Sleep4", None)
        add_mock_item(SwitchItem, "Unittest_Sleep5_req", None)
        add_mock_item(SwitchItem, "Unittest_Sleep6_req", None)

        config_full_day = LinkSleepConfig(
            items=LinkSleepItems(
                sleep_master="Unittest_Sleep1",
                sleep_request_slaves=["Unittest_Sleep2_req", "Unittest_Sleep3_req"],
            )
        )

        config_night = LinkSleepConfig(
            items=LinkSleepItems(
                sleep_master="Unittest_Sleep4",
                sleep_request_slaves=["Unittest_Sleep5_req", "Unittest_Sleep6_req"],
            ),
            parameter=LinkSleepParameter(
                start_time=datetime.time(22),
                end_time=datetime.time(10),
            ),
        )

        self._link_full_day = LinkSleep(config_full_day)
        self._link_night = LinkSleep(config_night)

    def test_init_with_feedback(self) -> None:
        """Test init with feedback item."""
        add_mock_item(SwitchItem, "Unittest_Link_Active", None)
        config = LinkSleepConfig(
            items=LinkSleepItems(
                sleep_master="Unittest_Sleep1",
                sleep_request_slaves=["Unittest_Sleep2_req", "Unittest_Sleep3_req"],
                link_active_feedback="Unittest_Link_Active",
            )
        )

        rule = LinkSleep(config)

        self.assertEqual("Unittest_Link_Active", rule._config.items.link_active_feedback.name)

    def test_check_time_in_window(self) -> None:
        """Test check_time_in_window."""
        TestCase = collections.namedtuple("TestCase", "start, end, now, expected_result")

        test_cases = [
            # full day
            TestCase(datetime.time(0), datetime.time(23, 59), datetime.time(0, 0), True),
            TestCase(datetime.time(0), datetime.time(23, 59), datetime.time(12), True),
            TestCase(datetime.time(0), datetime.time(23, 59), datetime.time(23, 59), True),
            # range during day
            TestCase(datetime.time(10), datetime.time(16), datetime.time(0, 0), False),
            TestCase(datetime.time(10), datetime.time(16), datetime.time(9, 59), False),
            TestCase(datetime.time(10), datetime.time(16), datetime.time(10), True),
            TestCase(datetime.time(10), datetime.time(16), datetime.time(10, 1), True),
            TestCase(datetime.time(10), datetime.time(16), datetime.time(15, 59), True),
            TestCase(datetime.time(10), datetime.time(16), datetime.time(16), True),
            TestCase(datetime.time(10), datetime.time(16), datetime.time(16, 1), False),
            TestCase(datetime.time(10), datetime.time(16), datetime.time(23, 59), False),
            # range over midnight day
            TestCase(datetime.time(22), datetime.time(5), datetime.time(12), False),
            TestCase(datetime.time(22), datetime.time(5), datetime.time(21, 59), False),
            TestCase(datetime.time(22), datetime.time(5), datetime.time(22), True),
            TestCase(datetime.time(22), datetime.time(5), datetime.time(22, 1), True),
            TestCase(datetime.time(22), datetime.time(5), datetime.time(0), True),
            TestCase(datetime.time(22), datetime.time(5), datetime.time(4, 59), True),
            TestCase(datetime.time(22), datetime.time(5), datetime.time(5), True),
            TestCase(datetime.time(22), datetime.time(5), datetime.time(5, 1), False),
        ]

        with unittest.mock.patch("datetime.datetime") as datetime_mock:
            now_mock = unittest.mock.MagicMock()
            datetime_mock.now.return_value = now_mock
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    now_mock.time.return_value = test_case.now

                    self._link_full_day._config.parameter.link_time_start = test_case.start
                    self._link_full_day._config.parameter.link_time_end = test_case.end

                    self.assertEqual(test_case.expected_result, self._link_full_day._check_time_in_window())

    def test_cb_master(self) -> None:
        """Test _cb_master."""
        # during active time
        with unittest.mock.patch.object(self._link_full_day, "_check_time_in_window", return_value=True):
            assert_item_value("Unittest_Sleep2_req", None)
            assert_item_value("Unittest_Sleep3_req", None)

            item_state_change_event("Unittest_Sleep1", "ON")
            assert_item_value("Unittest_Sleep2_req", "ON")
            assert_item_value("Unittest_Sleep3_req", "ON")

        # during inactive time
        with unittest.mock.patch.object(self._link_night, "_check_time_in_window", return_value=False):
            assert_item_value("Unittest_Sleep5_req", None)
            assert_item_value("Unittest_Sleep6_req", None)

            item_state_change_event("Unittest_Sleep4", "ON")
            assert_item_value("Unittest_Sleep5_req", None)
            assert_item_value("Unittest_Sleep6_req", None)

    def test_set_link_active_feedback(self) -> None:
        """Test _set_link_active_feedback."""
        with unittest.mock.patch.object(self._link_full_day._config.items, "link_active_feedback") as item_link_active_mock:
            self._link_full_day._set_link_active_feedback("ON")
        item_link_active_mock.oh_send_command.assert_called_once_with("ON")

        with unittest.mock.patch.object(self._link_full_day._config.items, "link_active_feedback") as item_link_active_mock:
            self._link_full_day._set_link_active_feedback("OFF")
        item_link_active_mock.oh_send_command.assert_called_once_with("OFF")
