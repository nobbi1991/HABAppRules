"""Test sleep rule."""

import collections
import datetime
import pathlib
import sys
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.system.config.sleep
import habapp_rules.system.sleep
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer


class TestSleep(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing presence rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep_Request", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Lock", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Lock_Request", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Display_Text", "")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Sleep_Unittest_Sleep_state", "")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "CustomState", "")

        config = habapp_rules.system.config.sleep.SleepConfig(
            items=habapp_rules.system.config.sleep.SleepItems(sleep="Unittest_Sleep", sleep_request="Unittest_Sleep_Request", lock="Unittest_Lock", lock_request="Unittest_Lock_Request", display_text="Unittest_Display_Text", state="CustomState")
        )

        self._sleep = habapp_rules.system.sleep.Sleep(config)

    def test_init_with_none(self) -> None:
        """Test __init__ with None values."""
        tests.helper.oh_item.set_state("Unittest_Sleep", None)
        tests.helper.oh_item.set_state("Unittest_Sleep_Request", None)
        tests.helper.oh_item.set_state("Unittest_Lock", None)
        tests.helper.oh_item.set_state("Unittest_Lock_Request", None)
        tests.helper.oh_item.set_state("Unittest_Display_Text", None)
        tests.helper.oh_item.set_state("CustomState", None)

        config = habapp_rules.system.config.sleep.SleepConfig(
            items=habapp_rules.system.config.sleep.SleepItems(sleep="Unittest_Sleep", sleep_request="Unittest_Sleep_Request", lock="Unittest_Lock", lock_request="Unittest_Lock_Request", display_text="Unittest_Display_Text", state="CustomState")
        )

        habapp_rules.system.sleep.Sleep(config)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        presence_graph = tests.helper.graph_machines.GraphMachineTimer(model=self._sleep, states=self._sleep.states, transitions=self._sleep.trans, initial=self._sleep.state, show_conditions=True)

        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "Sleep"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)
        presence_graph.get_graph().draw(picture_dir / "Sleep.png", format="png", prog="dot")

    def test_enums(self) -> None:
        """Test if all enums from __init__.py are implemented."""
        implemented_states = list(self._sleep.state_machine.states)
        enum_states = [state.value for state in habapp_rules.system.SleepState] + ["initial"]
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

        config = habapp_rules.system.config.sleep.SleepConfig(
            items=habapp_rules.system.config.sleep.SleepItems(sleep="Unittest_Sleep", sleep_request="Unittest_Sleep_Request", lock="Unittest_Lock", lock_request="Unittest_Lock_Request", display_text="Unittest_Display_Text", state="CustomState")
        )

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_Sleep_Request", test_case.sleep_request_state)
                tests.helper.oh_item.set_state("Unittest_Lock_Request", test_case.lock_request_state)

                sleep = habapp_rules.system.sleep.Sleep(config)

                self.assertEqual(sleep.sleep_request_active, test_case.sleep_request_state == "ON", test_case)
                self.assertEqual(sleep.lock_request_active, test_case.lock_request_state == "ON", test_case)
                tests.helper.oh_item.assert_value("Unittest_Sleep", test_case.sleep_request_state)
                tests.helper.oh_item.assert_value("Unittest_Lock", test_case.lock_state)

    def test_get_initial_state(self) -> None:
        """Test getting initial state."""
        TestCase = collections.namedtuple("TestCase", "sleep_request, lock_request, expected_state")

        test_cases = [
            TestCase(sleep_request="OFF", lock_request="OFF", expected_state="awake"),
            TestCase(sleep_request="OFF", lock_request="ON", expected_state="locked"),
            TestCase(sleep_request="ON", lock_request="OFF", expected_state="sleeping"),
            TestCase(sleep_request="ON", lock_request="ON", expected_state="sleeping"),
            TestCase(sleep_request=None, lock_request="ON", expected_state="locked"),
            TestCase(sleep_request=None, lock_request="OFF", expected_state="default"),
            TestCase(sleep_request="ON", lock_request=None, expected_state="sleeping"),
            TestCase(sleep_request="OFF", lock_request=None, expected_state="awake"),
            TestCase(sleep_request=None, lock_request=None, expected_state="default"),
        ]

        for test_case in test_cases:
            tests.helper.oh_item.set_state("Unittest_Sleep_Request", test_case.sleep_request)
            tests.helper.oh_item.set_state("Unittest_Lock_Request", test_case.lock_request)

            self.assertEqual(self._sleep._get_initial_state("default"), test_case.expected_state, test_case)

    def test__get_display_text(self) -> None:
        """Test getting display text."""
        TestCase = collections.namedtuple("TestCase", "state, text")
        test_cases = [TestCase("awake", "Schlafen"), TestCase("pre_sleeping", "Guten Schlaf"), TestCase("sleeping", "Aufstehen"), TestCase("post_sleeping", "Guten Morgen"), TestCase("locked", "Gesperrt"), TestCase(None, "")]

        for test_case in test_cases:
            self._sleep.state = test_case.state
            self.assertEqual(test_case.text, self._sleep._Sleep__get_display_text())

    def test_normal_cycle_all_items(self) -> None:
        """Test normal behavior with all items available."""
        # check initial state
        tests.helper.oh_item.assert_value("CustomState", "awake")

        # start sleeping
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
        self.assertEqual(self._sleep.state, "pre_sleeping")
        tests.helper.oh_item.assert_value("CustomState", "pre_sleeping")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "ON")
        tests.helper.oh_item.assert_value("Unittest_Lock", "ON")
        tests.helper.oh_item.assert_value("Unittest_Display_Text", "Guten Schlaf")
        self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

        # pre_sleeping timeout -> sleep
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._sleep.state, "sleeping")
        tests.helper.oh_item.assert_value("CustomState", "sleeping")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "ON")
        tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Display_Text", "Aufstehen")

        # stop sleeping
        self.transitions_timer_mock.reset_mock()
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "OFF", "ON")
        self.assertEqual(self._sleep.state, "post_sleeping")
        tests.helper.oh_item.assert_value("CustomState", "post_sleeping")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Lock", "ON")
        tests.helper.oh_item.assert_value("Unittest_Display_Text", "Guten Morgen")
        self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

        # post_sleeping timeout -> awake
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._sleep.state, "awake")
        tests.helper.oh_item.assert_value("CustomState", "awake")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Display_Text", "Schlafen")

    def test_lock_transitions(self) -> None:
        """Test all transitions from and to locked state."""
        # check correct initial state
        tests.helper.oh_item.assert_value("CustomState", "awake")
        tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")

        # set lock_request. expected: locked state, lock active, sleep off
        tests.helper.oh_item.send_command("Unittest_Lock_Request", "ON", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Lock", "ON")
        tests.helper.oh_item.assert_value("CustomState", "locked")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

        # release lock and come back to awake state
        tests.helper.oh_item.send_command("Unittest_Lock_Request", "OFF", "ON")
        tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")
        tests.helper.oh_item.assert_value("CustomState", "awake")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

        # set lock_request and shortly after send sleep request -> locked expected
        tests.helper.oh_item.send_command("Unittest_Lock_Request", "ON", "OFF")
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Sleep_Request", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Lock", "ON")
        tests.helper.oh_item.assert_value("CustomState", "locked")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

        # release lock and jump back to awake
        tests.helper.oh_item.send_command("Unittest_Lock_Request", "OFF", "ON")
        tests.helper.oh_item.assert_value("Unittest_Lock", "OFF")
        tests.helper.oh_item.assert_value("CustomState", "awake")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")

        # start sleeping
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
        tests.helper.oh_item.assert_value("CustomState", "pre_sleeping")

        # activate lock, remove sleep request and wait all timer -> expected state == locked
        tests.helper.oh_item.send_command("Unittest_Lock_Request", "ON", "OFF")
        tests.helper.oh_item.assert_value("CustomState", "pre_sleeping")
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        tests.helper.oh_item.assert_value("CustomState", "sleeping")
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "OFF", "ON")
        tests.helper.oh_item.assert_value("CustomState", "post_sleeping")
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        tests.helper.oh_item.assert_value("CustomState", "locked")

        # go back to pre_sleeping and check lock + end sleep in pre_sleeping -> expected state = locked
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
        tests.helper.oh_item.assert_value("CustomState", "locked")
        tests.helper.oh_item.send_command("Unittest_Lock_Request", "OFF", "ON")
        tests.helper.oh_item.assert_value("CustomState", "awake")
        tests.helper.oh_item.send_command("Unittest_Lock_Request", "ON", "OFF")
        tests.helper.oh_item.assert_value("CustomState", "locked")

    def test_request_changed(self) -> None:
        """Test transitions when sleep request is changed at pre_sleeping or post_sleeping state."""
        tests.helper.oh_item.set_state("Unittest_Sleep_Request", "ON")
        self._sleep.to_pre_sleeping()
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "OFF")
        tests.helper.oh_item.assert_value("CustomState", "awake")

        tests.helper.oh_item.set_state("Unittest_Sleep_Request", "OFF")
        self._sleep.to_post_sleeping()
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON")
        tests.helper.oh_item.assert_value("CustomState", "pre_sleeping")

    def test_minimal_items(self) -> None:
        """Test Sleeping class with minimal set of items."""
        # delete sleep rule from init
        self.unload_rule(self._runner.loaded_rules[0])

        tests.helper.oh_item.remove_mocked_item_by_name("Unittest_Lock")
        tests.helper.oh_item.remove_mocked_item_by_name("Unittest_Lock_Request")
        tests.helper.oh_item.remove_mocked_item_by_name("Unittest_Display_Text")

        config = habapp_rules.system.config.sleep.SleepConfig(
            items=habapp_rules.system.config.sleep.SleepItems(
                sleep="Unittest_Sleep",
                sleep_request="Unittest_Sleep_Request",
                state="H_Sleep_Unittest_Sleep_state",
            )
        )

        sleep = habapp_rules.system.sleep.Sleep(config)

        self.assertIsNone(sleep._config.items.display_text)
        self.assertIsNone(sleep._config.items.lock)
        self.assertIsNone(sleep._config.items.lock_request)

        # check initial state
        tests.helper.oh_item.assert_value("CustomState", "awake")

        # start sleeping
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "ON", "OFF")
        self.assertEqual(sleep.state, "pre_sleeping")
        tests.helper.oh_item.assert_value("H_Sleep_Unittest_Sleep_state", "pre_sleeping")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "ON")
        self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

        # pre_sleeping timeout -> sleep
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual(sleep.state, "sleeping")
        tests.helper.oh_item.assert_value("H_Sleep_Unittest_Sleep_state", "sleeping")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "ON")

        # stop sleeping
        self.transitions_timer_mock.reset_mock()
        tests.helper.oh_item.send_command("Unittest_Sleep_Request", "OFF", "ON")
        self.assertEqual(sleep.state, "post_sleeping")
        tests.helper.oh_item.assert_value("H_Sleep_Unittest_Sleep_state", "post_sleeping")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")
        self.transitions_timer_mock.assert_called_with(3, unittest.mock.ANY, args=unittest.mock.ANY)

        # post_sleeping timeout -> awake
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual(sleep.state, "awake")
        tests.helper.oh_item.assert_value("H_Sleep_Unittest_Sleep_state", "awake")
        tests.helper.oh_item.assert_value("Unittest_Sleep", "OFF")


class TestLinkSleep(tests.helper.test_case_base.TestCaseBase):
    """Test LinkSleep."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep2_req", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep3_req", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep4", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep5_req", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep6_req", None)

        config_full_day = habapp_rules.system.config.sleep.LinkSleepConfig(
            items=habapp_rules.system.config.sleep.LinkSleepItems(
                sleep_master="Unittest_Sleep1",
                sleep_request_slaves=["Unittest_Sleep2_req", "Unittest_Sleep3_req"],
            )
        )

        config_night = habapp_rules.system.config.sleep.LinkSleepConfig(
            items=habapp_rules.system.config.sleep.LinkSleepItems(
                sleep_master="Unittest_Sleep4",
                sleep_request_slaves=["Unittest_Sleep5_req", "Unittest_Sleep6_req"],
            ),
            parameter=habapp_rules.system.config.sleep.LinkSleepParameter(
                start_time=datetime.time(22),
                end_time=datetime.time(10),
            ),
        )

        self._link_full_day = habapp_rules.system.sleep.LinkSleep(config_full_day)
        self._link_night = habapp_rules.system.sleep.LinkSleep(config_night)

    def test_init_with_feedback(self) -> None:
        """Test init with feedback item."""
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Link_Active", None)
        config = habapp_rules.system.config.sleep.LinkSleepConfig(
            items=habapp_rules.system.config.sleep.LinkSleepItems(
                sleep_master="Unittest_Sleep1",
                sleep_request_slaves=["Unittest_Sleep2_req", "Unittest_Sleep3_req"],
                link_active_feedback="Unittest_Link_Active",
            )
        )

        rule = habapp_rules.system.sleep.LinkSleep(config)

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
            tests.helper.oh_item.assert_value("Unittest_Sleep2_req", None)
            tests.helper.oh_item.assert_value("Unittest_Sleep3_req", None)

            tests.helper.oh_item.item_state_change_event("Unittest_Sleep1", "ON")
            tests.helper.oh_item.assert_value("Unittest_Sleep2_req", "ON")
            tests.helper.oh_item.assert_value("Unittest_Sleep3_req", "ON")

        # during inactive time
        with unittest.mock.patch.object(self._link_night, "_check_time_in_window", return_value=False):
            tests.helper.oh_item.assert_value("Unittest_Sleep5_req", None)
            tests.helper.oh_item.assert_value("Unittest_Sleep6_req", None)

            tests.helper.oh_item.item_state_change_event("Unittest_Sleep4", "ON")
            tests.helper.oh_item.assert_value("Unittest_Sleep5_req", None)
            tests.helper.oh_item.assert_value("Unittest_Sleep6_req", None)

    def test_set_link_active_feedback(self) -> None:
        """Test _set_link_active_feedback."""
        with unittest.mock.patch.object(self._link_full_day._config.items, "link_active_feedback") as item_link_active_mock:
            self._link_full_day._set_link_active_feedback("ON")
        item_link_active_mock.oh_send_command.assert_called_once_with("ON")

        with unittest.mock.patch.object(self._link_full_day._config.items, "link_active_feedback") as item_link_active_mock:
            self._link_full_day._set_link_active_feedback("OFF")
        item_link_active_mock.oh_send_command.assert_called_once_with("OFF")
