"""Test Presence rule."""

import collections
import sys
import unittest
import unittest.mock

from HABApp.openhab.events import ItemStateChangedEvent
from HABApp.openhab.items import ContactItem, StringItem, SwitchItem

from habapp_rules.system import PresenceState
from habapp_rules.system.config.presence import PresenceConfig, PresenceItems
from habapp_rules.system.presence import Presence
from tests.helper.graph_machines import create_state_graphs
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    send_command,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBaseStateMachine
from tests.helper.timer import call_timeout


class TestPresence(TestCaseBaseStateMachine):
    """Tests cases for testing presence rule."""

    def setUp(self) -> None:
        """Setup test case."""
        super().setUp()

        add_mock_item(ContactItem, "Unittest_Door1", "CLOSED")
        add_mock_item(ContactItem, "Unittest_Door2", "CLOSED")
        add_mock_item(SwitchItem, "Unittest_Leaving", "OFF")
        add_mock_item(SwitchItem, "Unittest_Phone1", "ON")
        add_mock_item(SwitchItem, "Unittest_Phone2", "OFF")
        add_mock_item(StringItem, "CustomState", "")
        add_mock_item(StringItem, "H_Presence_Unittest_Presence_state", "")
        add_mock_item(SwitchItem, "Unittest_Presence", "ON")

        config = PresenceConfig(items=PresenceItems(presence="Unittest_Presence", leaving="Unittest_Leaving", outdoor_doors=["Unittest_Door1", "Unittest_Door2"], phones=["Unittest_Phone1", "Unittest_Phone2"], state="CustomState"))

        self.habapp_countdown_mock_patcher = unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.countdown")
        self.addCleanup(self.habapp_countdown_mock_patcher.stop)
        self.habapp_countdown_mock = self.habapp_countdown_mock_patcher.start()

        self._presence = Presence(config)

    def test_init_with_none(self) -> None:
        """Test __init__ with None values."""
        set_item_state("Unittest_Presence", None)
        set_item_state("Unittest_Door1", None)
        set_item_state("Unittest_Door2", None)
        set_item_state("Unittest_Leaving", None)
        set_item_state("Unittest_Phone1", None)
        set_item_state("Unittest_Phone2", None)
        set_item_state("CustomState", None)

        config = PresenceConfig(items=PresenceItems(presence="Unittest_Presence", leaving="Unittest_Leaving", outdoor_doors=["Unittest_Door1", "Unittest_Door2"], phones=["Unittest_Phone1", "Unittest_Phone2"], state="CustomState"))

        Presence(config)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        create_state_graphs(self._presence, "Presence")

    def test_minimal_init(self) -> None:
        """Test init with minimal set of arguments."""
        config = PresenceConfig(items=PresenceItems(presence="Unittest_Presence", leaving="Unittest_Leaving", state="CustomState"))

        presence_min = Presence(config)

        self.assertEqual([], presence_min._config.items.phones)
        self.assertEqual([], presence_min._config.items.outdoor_doors)

    def test_enums(self) -> None:
        """Test if all enums from __init__.py are implemented."""
        implemented_states = list(self._presence.state_machine.states)
        enum_states = [state.value for state in PresenceState]
        self.assertEqual(len(enum_states), len(implemented_states))
        self.assertTrue(all(state in enum_states for state in implemented_states))

    def test__init__(self) -> None:
        """Test init."""
        assert_item_value("CustomState", "Presence")
        self.assertEqual(self._presence.state, "Presence")

    def test_get_initial_state(self) -> None:
        """Test getting correct initial state."""
        Testcase = collections.namedtuple("Testcase", "presence, outside_doors, leaving, phones, expected_result")

        testcases = [
            # presence ON | leaving OFF
            Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=[], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["ON"], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["OFF"], expected_result="Leaving"),
            Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=[], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["OFF"], expected_result="Leaving"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=[], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["OFF"], expected_result="Leaving"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="Leaving"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="Presence"),
            # presence ON | leaving ON
            Testcase(presence="ON", leaving="ON", outside_doors=[], phones=[], expected_result="Leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["ON"], expected_result="Presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["OFF"], expected_result="Leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=[], expected_result="Leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["OFF"], expected_result="Leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=[], expected_result="Leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["OFF"], expected_result="Leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="Leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="Leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="Presence"),
            # presence OFF | leaving OFF
            Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=[], expected_result="Absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["ON"], expected_result="Presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["OFF"], expected_result="Absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=[], expected_result="Absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["OFF"], expected_result="Absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=[], expected_result="Absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["OFF"], expected_result="Absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="Presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="Absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="Presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="Absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="Presence"),
            # all None
            Testcase(presence=None, leaving=None, outside_doors=[None, None], phones=[None, None], expected_result="default"),
        ]

        for testcase in testcases:
            with self.subTest(testcase=testcase):
                self._presence._config.items.presence.value = testcase.presence
                self._presence._config.items.leaving.value = testcase.leaving

                self._presence._config.items.outdoor_doors = [ContactItem(f"Unittest_Door{idx}", state) for idx, state in enumerate(testcase.outside_doors)]
                self._presence._config.items.phones = [SwitchItem(f"Unittest_Phone{idx}", state) for idx, state in enumerate(testcase.phones)]

                self.assertEqual(self._presence._get_initial_state("default"), testcase.expected_result, f"failed testcase: {testcase}")

    def test_get_initial_state_extra(self) -> None:
        """Test getting correct initial state for special cases."""
        # current state value is long_absence
        self._presence._config.items.presence.value = "OFF"
        self._presence._config.items.leaving.value = "OFF"
        self._presence._config.items.state.value = "LongAbsence"
        self._presence._config.items.outdoor_doors = []

        # no phones
        self._presence._config.items.phones = []
        self.assertEqual(self._presence._get_initial_state("default"), "LongAbsence")

        # with phones
        self._presence._config.items.phones = [SwitchItem("Unittest_Phone1")]
        self.assertEqual(self._presence._get_initial_state("default"), "LongAbsence")

    def test_presence_trough_doors(self) -> None:
        """Test if outside doors set presence correctly."""
        send_command("Unittest_Presence", "OFF")
        self._presence.state_machine.set_state("Absence")
        self.assertEqual(self._presence.state, "Absence")

        send_command("Unittest_Door1", "CLOSED", "CLOSED")
        self.assertEqual(self._presence.state, "Absence")

        send_command("Unittest_Door1", "OPEN", "CLOSED")
        self.assertEqual(self._presence.state, "Presence")
        assert_item_value("Unittest_Presence", "ON")

        send_command("Unittest_Door1", "OPEN", "CLOSED")
        self.assertEqual(self._presence.state, "Presence")

        send_command("Unittest_Door1", "CLOSED", "CLOSED")
        self.assertEqual(self._presence.state, "Presence")

    def test_normal_leaving(self) -> None:
        """Test if 'normal' leaving works correctly."""
        self._presence.state_machine.set_state("Presence")
        self.assertEqual(self._presence.state, "Presence")

        send_command("Unittest_Leaving", "OFF", "ON")
        self.assertEqual(self._presence.state, "Presence")

        send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "Leaving")
        self.transitions_timer_mock.assert_called_with(300, unittest.mock.ANY, args=unittest.mock.ANY)

        # call timeout and check if absence is active
        call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "Absence")

        # leaving switches to on again -> state should be leaving again
        send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "Leaving")

        # test if also long absence is working
        self._presence.state = "LongAbsence"
        send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "Leaving")

    def test_abort_leaving(self) -> None:
        """Test aborting of leaving state."""
        self._presence.state_machine.set_state("Presence")
        self.assertEqual(self._presence.state, "Presence")
        set_item_state("Unittest_Leaving", "ON")

        send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "Leaving")
        assert_item_value("Unittest_Leaving", "ON")

        send_command("Unittest_Leaving", "OFF", "ON")
        self.assertEqual(self._presence.state, "Presence")
        assert_item_value("Unittest_Leaving", "OFF")

    def test_abort_leaving_after_last_phone(self) -> None:
        """Test aborting of leaving which was started through last phone leaving."""
        self._presence.state_machine.set_state("Presence")
        set_item_state("Unittest_Phone1", "ON")

        send_command("Unittest_Phone1", "OFF", "ON")
        call_timeout(self.habapp_countdown_mock)
        self.assertEqual(self._presence.state, "Leaving")
        assert_item_value("Unittest_Leaving", "ON")

        send_command("Unittest_Leaving", "OFF", "ON")
        self.assertEqual(self._presence.state, "Presence")

        send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "Presence")

        send_command("Unittest_Phone1", "OFF", "ON")
        call_timeout(self.habapp_countdown_mock)
        self.assertEqual(self._presence.state, "Leaving")
        assert_item_value("Unittest_Leaving", "ON")

    def test_leaving_with_phones(self) -> None:
        """Test if leaving and absence is correct if phones appear/disappear during or after leaving."""
        # set initial states
        set_item_state("Unittest_Phone1", "ON")
        set_item_state("Unittest_Phone2", "OFF")
        self._presence.state_machine.set_state("Presence")
        send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "Leaving")

        # leaving on, last phone disappears
        send_command("Unittest_Phone1", "OFF", "ON")
        self.assertEqual(self._presence.state, "Leaving")

        # leaving on, first phone appears
        send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "Presence")

        # leaving on, second phone appears
        send_command("Unittest_Phone2", "ON", "OFF")
        self.assertEqual(self._presence.state, "Presence")

        # leaving on, both phones leaving
        self._presence.state_machine.set_state("Leaving")
        send_command("Unittest_Phone1", "OFF", "ON")
        send_command("Unittest_Phone2", "OFF", "ON")
        self.assertEqual(self._presence.state, "Leaving")

        # absence on, one disappears, one stays online
        send_command("Unittest_Phone1", "ON", "OFF")
        send_command("Unittest_Phone2", "ON", "OFF")
        call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "Absence")
        send_command("Unittest_Phone1", "OFF", "ON")
        self.assertEqual(self._presence.state, "Absence")

        # absence on, two phones disappears
        send_command("Unittest_Phone2", "OFF", "ON")
        self.assertEqual(self._presence.state, "Absence")

    def test__set_leaving_through_phone(self) -> None:
        """Test if leaving_detected is called correctly after timeout of __phone_absence_timer."""
        TestCase = collections.namedtuple("TestCase", "state, leaving_detected_called")

        test_cases = [TestCase("Presence", True), TestCase("Leaving", False), TestCase("Absence", False), TestCase("LongAbsence", False)]

        for test_case in test_cases:
            with unittest.mock.patch.object(self._presence, "trigger") as trigger_mock:
                self._presence.state = test_case.state
                self._presence._Presence__set_leaving_through_phone()
            if test_case.leaving_detected_called:
                trigger_mock.assert_called_once_with("leaving_detected")
            else:
                trigger_mock.assert_not_called()

    def test_long_absence(self) -> None:
        """Test entering long_absence and leaving it."""
        # set initial state
        self._presence.state_machine.set_state("Presence")
        set_item_state("Unittest_Presence", "ON")

        # go to absence
        self._presence.absence_detected()
        self.assertEqual(self._presence.state, "Absence")
        assert_item_value("Unittest_Presence", "OFF")

        # check if timeout started, and stop the mocked timer
        self.transitions_timer_mock.assert_called_with(1.5 * 24 * 3600, unittest.mock.ANY, args=unittest.mock.ANY)
        call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "LongAbsence")
        assert_item_value("Unittest_Presence", "OFF")

        # check if presence is set after door open
        self._presence._cb_outside_door(ItemStateChangedEvent("Unittest_Door1", "OPEN", "CLOSED"))
        self.assertEqual(self._presence.state, "Presence")
        assert_item_value("Unittest_Presence", "ON")

    def test_manual_change(self) -> None:
        """Test if change of presence object is setting correct state."""
        # send manual off from presence
        self._presence.state_machine.set_state("Presence")
        send_command("Unittest_Presence", "ON", "OFF")
        self._presence._cb_presence(ItemStateChangedEvent("Unittest_Presence", "OFF", "ON"))
        self.assertEqual(self._presence.state, "Absence")
        send_command("Unittest_Presence", "OFF", "ON")

        # send manual off from leaving
        self._presence.state_machine.set_state("Leaving")
        send_command("Unittest_Presence", "ON", "OFF")
        self._presence._cb_presence(ItemStateChangedEvent("Unittest_Presence", "OFF", "ON"))
        self.assertEqual(self._presence.state, "Absence")
        send_command("Unittest_Presence", "OFF", "ON")

        # send manual on from absence
        self._presence.state_machine.set_state("Absence")
        send_command("Unittest_Presence", "OFF", "ON")
        self._presence._cb_presence(ItemStateChangedEvent("Unittest_Presence", "ON", "OFF"))
        self.assertEqual(self._presence.state, "Presence")
        send_command("Unittest_Presence", "ON", "OFF")

        # send manual on from long_absence
        self._presence.state_machine.set_state("LongAbsence")
        send_command("Unittest_Presence", "OFF", "ON")
        self._presence._cb_presence(ItemStateChangedEvent("Unittest_Presence", "ON", "OFF"))
        self.assertEqual(self._presence.state, "Presence")
        send_command("Unittest_Presence", "ON", "OFF")

    def test_phones(self) -> None:
        """Test if presence is set correctly through phones."""
        # first phone switches to ON -> presence expected
        self._presence.state_machine.set_state("Absence")
        send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "Presence")
        self.habapp_countdown_mock.return_value.reset.assert_not_called()

        # second phone switches to ON -> no change expected
        send_command("Unittest_Phone2", "ON", "OFF")
        self.assertEqual(self._presence.state, "Presence")
        self.habapp_countdown_mock.return_value.reset.assert_not_called()

        # second phone switches to OFF -> no change expected
        send_command("Unittest_Phone2", "OFF", "ON")
        self.assertEqual(self._presence.state, "Presence")
        self.habapp_countdown_mock.return_value.reset.assert_not_called()

        # first phone switches to OFF -> timer should be started
        send_command("Unittest_Phone1", "OFF", "ON")
        self.assertEqual(self._presence.state, "Presence")
        self.habapp_countdown_mock.return_value.reset.assert_called_once()
        call_timeout(self.habapp_countdown_mock)
        self.assertEqual(self._presence.state, "Leaving")

        # phone appears during leaving -> leaving expected
        self.habapp_countdown_mock.return_value.stop.reset_mock()
        send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "Presence")
        self.habapp_countdown_mock.return_value.stop.assert_called_once()

        # timeout is over -> absence expected
        call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "Absence")
