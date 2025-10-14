"""Test Presence rule."""

import collections
import pathlib
import sys
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.system.config.presence
import habapp_rules.system.presence
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer


class TestPresence(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing presence rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door1", "CLOSED")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door2", "CLOSED")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Leaving", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone1", "ON")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone2", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "CustomState", "")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Presence_Unittest_Presence_state", "")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Presence", "ON")

        config = habapp_rules.system.config.presence.PresenceConfig(
            items=habapp_rules.system.config.presence.PresenceItems(presence="Unittest_Presence", leaving="Unittest_Leaving", outdoor_doors=["Unittest_Door1", "Unittest_Door2"], phones=["Unittest_Phone1", "Unittest_Phone2"], state="CustomState")
        )

        self.habapp_countdown_mock_patcher = unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.countdown")
        self.addCleanup(self.habapp_countdown_mock_patcher.stop)
        self.habapp_countdown_mock = self.habapp_countdown_mock_patcher.start()

        self._presence = habapp_rules.system.presence.Presence(config)

    def test_init_with_none(self) -> None:
        """Test __init__ with None values."""
        tests.helper.oh_item.set_state("Unittest_Presence", None)
        tests.helper.oh_item.set_state("Unittest_Door1", None)
        tests.helper.oh_item.set_state("Unittest_Door2", None)
        tests.helper.oh_item.set_state("Unittest_Leaving", None)
        tests.helper.oh_item.set_state("Unittest_Phone1", None)
        tests.helper.oh_item.set_state("Unittest_Phone2", None)
        tests.helper.oh_item.set_state("CustomState", None)

        config = habapp_rules.system.config.presence.PresenceConfig(
            items=habapp_rules.system.config.presence.PresenceItems(presence="Unittest_Presence", leaving="Unittest_Leaving", outdoor_doors=["Unittest_Door1", "Unittest_Door2"], phones=["Unittest_Phone1", "Unittest_Phone2"], state="CustomState")
        )

        habapp_rules.system.presence.Presence(config)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        presence_graph = tests.helper.graph_machines.GraphMachineTimer(model=self._presence, states=self._presence.states, transitions=self._presence.trans, initial=self._presence.state, show_conditions=True)

        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "Presence"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)
        presence_graph.get_graph().draw(picture_dir / "Presence.png", format="png", prog="dot")

    def test_minimal_init(self) -> None:
        """Test init with minimal set of arguments."""
        config = habapp_rules.system.config.presence.PresenceConfig(items=habapp_rules.system.config.presence.PresenceItems(presence="Unittest_Presence", leaving="Unittest_Leaving", state="CustomState"))

        presence_min = habapp_rules.system.presence.Presence(config)

        self.assertEqual([], presence_min._config.items.phones)
        self.assertEqual([], presence_min._config.items.outdoor_doors)

    def test_enums(self) -> None:
        """Test if all enums from __init__.py are implemented."""
        implemented_states = list(self._presence.state_machine.states)
        enum_states = [state.value for state in habapp_rules.system.PresenceState] + ["initial"]
        self.assertEqual(len(enum_states), len(implemented_states))
        self.assertTrue(all(state in enum_states for state in implemented_states))

    def test__init__(self) -> None:
        """Test init."""
        tests.helper.oh_item.assert_value("CustomState", "presence")
        self.assertEqual(self._presence.state, "presence")

    def test_get_initial_state(self) -> None:
        """Test getting correct initial state."""
        Testcase = collections.namedtuple("Testcase", "presence, outside_doors, leaving, phones, expected_result")

        testcases = [
            # presence ON | leaving OFF
            Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=[], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["ON"], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["OFF"], expected_result="leaving"),
            Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=[], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["ON"], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["OFF"], expected_result="leaving"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=[], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["ON"], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["OFF"], expected_result="leaving"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="presence"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="leaving"),
            Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="presence"),
            # presence ON | leaving ON
            Testcase(presence="ON", leaving="ON", outside_doors=[], phones=[], expected_result="leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["ON"], expected_result="presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["OFF"], expected_result="leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=[], expected_result="leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["ON"], expected_result="presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["OFF"], expected_result="leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=[], expected_result="leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["ON"], expected_result="presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["OFF"], expected_result="leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="presence"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="leaving"),
            Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="presence"),
            # presence OFF | leaving OFF
            Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=[], expected_result="absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["ON"], expected_result="presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["OFF"], expected_result="absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=[], expected_result="absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["ON"], expected_result="presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["OFF"], expected_result="absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=[], expected_result="absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["ON"], expected_result="presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["OFF"], expected_result="absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="presence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="absence"),
            Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="presence"),
            # all None
            Testcase(presence=None, leaving=None, outside_doors=[None, None], phones=[None, None], expected_result="default"),
        ]

        for testcase in testcases:
            with self.subTest(testcase=testcase):
                self._presence._config.items.presence.value = testcase.presence
                self._presence._config.items.leaving.value = testcase.leaving

                self._presence._config.items.outdoor_doors = [HABApp.openhab.items.ContactItem(f"Unittest_Door{idx}", state) for idx, state in enumerate(testcase.outside_doors)]
                self._presence._config.items.phones = [HABApp.openhab.items.SwitchItem(f"Unittest_Phone{idx}", state) for idx, state in enumerate(testcase.phones)]

                self.assertEqual(self._presence._get_initial_state("default"), testcase.expected_result, f"failed testcase: {testcase}")

    def test_get_initial_state_extra(self) -> None:
        """Test getting correct initial state for special cases."""
        # current state value is long_absence
        self._presence._config.items.presence.value = "OFF"
        self._presence._config.items.leaving.value = "OFF"
        self._presence._config.items.state.value = "long_absence"
        self._presence._config.items.outdoor_doors = []

        # no phones
        self._presence._config.items.phones = []
        self.assertEqual(self._presence._get_initial_state("default"), "long_absence")

        # with phones
        self._presence._config.items.phones = [HABApp.openhab.items.SwitchItem("Unittest_Phone1")]
        self.assertEqual(self._presence._get_initial_state("default"), "long_absence")

    def test_presence_trough_doors(self) -> None:
        """Test if outside doors set presence correctly."""
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF")
        self._presence.state_machine.set_state("absence")
        self.assertEqual(self._presence.state, "absence")

        tests.helper.oh_item.send_command("Unittest_Door1", "CLOSED", "CLOSED")
        self.assertEqual(self._presence.state, "absence")

        tests.helper.oh_item.send_command("Unittest_Door1", "OPEN", "CLOSED")
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.assert_value("Unittest_Presence", "ON")

        tests.helper.oh_item.send_command("Unittest_Door1", "OPEN", "CLOSED")
        self.assertEqual(self._presence.state, "presence")

        tests.helper.oh_item.send_command("Unittest_Door1", "CLOSED", "CLOSED")
        self.assertEqual(self._presence.state, "presence")

    def test_normal_leaving(self) -> None:
        """Test if 'normal' leaving works correctly."""
        self._presence.state_machine.set_state("presence")
        self.assertEqual(self._presence.state, "presence")

        tests.helper.oh_item.send_command("Unittest_Leaving", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")

        tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "leaving")
        self.transitions_timer_mock.assert_called_with(300, unittest.mock.ANY, args=unittest.mock.ANY)

        # call timeout and check if absence is active
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "absence")

        # leaving switches to on again -> state should be leaving again
        tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "leaving")

        # test if also long absence is working
        self._presence.state = "long_absence"
        tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "leaving")

    def test_abort_leaving(self) -> None:
        """Test aborting of leaving state."""
        self._presence.state_machine.set_state("presence")
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.set_state("Unittest_Leaving", "ON")

        tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "leaving")
        tests.helper.oh_item.assert_value("Unittest_Leaving", "ON")

        tests.helper.oh_item.send_command("Unittest_Leaving", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.assert_value("Unittest_Leaving", "OFF")

    def test_abort_leaving_after_last_phone(self) -> None:
        """Test aborting of leaving which was started through last phone leaving."""
        self._presence.state_machine.set_state("presence")
        tests.helper.oh_item.set_state("Unittest_Phone1", "ON")

        tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
        tests.helper.timer.call_timeout(self.habapp_countdown_mock)
        self.assertEqual(self._presence.state, "leaving")
        tests.helper.oh_item.assert_value("Unittest_Leaving", "ON")

        tests.helper.oh_item.send_command("Unittest_Leaving", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")

        tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")

        tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
        tests.helper.timer.call_timeout(self.habapp_countdown_mock)
        self.assertEqual(self._presence.state, "leaving")
        tests.helper.oh_item.assert_value("Unittest_Leaving", "ON")

    def test_leaving_with_phones(self) -> None:
        """Test if leaving and absence is correct if phones appear/disappear during or after leaving."""
        # set initial states
        tests.helper.oh_item.set_state("Unittest_Phone1", "ON")
        tests.helper.oh_item.set_state("Unittest_Phone2", "OFF")
        self._presence.state_machine.set_state("presence")
        tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "leaving")

        # leaving on, last phone disappears
        tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
        self.assertEqual(self._presence.state, "leaving")

        # leaving on, first phone appears
        tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")

        # leaving on, second phone appears
        tests.helper.oh_item.send_command("Unittest_Phone2", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")

        # leaving on, both phones leaving
        self._presence.state_machine.set_state("leaving")
        tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
        tests.helper.oh_item.send_command("Unittest_Phone2", "OFF", "ON")
        self.assertEqual(self._presence.state, "leaving")

        # absence on, one disappears, one stays online
        tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
        tests.helper.oh_item.send_command("Unittest_Phone2", "ON", "OFF")
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "absence")
        tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
        self.assertEqual(self._presence.state, "absence")

        # absence on, two phones disappears
        tests.helper.oh_item.send_command("Unittest_Phone2", "OFF", "ON")
        self.assertEqual(self._presence.state, "absence")

    def test__set_leaving_through_phone(self) -> None:
        """Test if leaving_detected is called correctly after timeout of __phone_absence_timer."""
        TestCase = collections.namedtuple("TestCase", "state, leaving_detected_called")

        test_cases = [TestCase("presence", True), TestCase("leaving", False), TestCase("absence", False), TestCase("long_absence", False)]

        for test_case in test_cases:
            with unittest.mock.patch.object(self._presence, "leaving_detected") as leaving_detected_mock:
                self._presence.state = test_case.state
                self._presence._Presence__set_leaving_through_phone()
            self.assertEqual(test_case.leaving_detected_called, leaving_detected_mock.called)

    def test_long_absence(self) -> None:
        """Test entering long_absence and leaving it."""
        # set initial state
        self._presence.state_machine.set_state("presence")
        tests.helper.oh_item.set_state("Unittest_Presence", "ON")

        # go to absence
        self._presence.absence_detected()
        self.assertEqual(self._presence.state, "absence")
        tests.helper.oh_item.assert_value("Unittest_Presence", "OFF")

        # check if timeout started, and stop the mocked timer
        self.transitions_timer_mock.assert_called_with(1.5 * 24 * 3600, unittest.mock.ANY, args=unittest.mock.ANY)
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "long_absence")
        tests.helper.oh_item.assert_value("Unittest_Presence", "OFF")

        # check if presence is set after door open
        self._presence._cb_outside_door(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Door1", "OPEN", "CLOSED"))
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.assert_value("Unittest_Presence", "ON")

    def test_manual_change(self) -> None:
        """Test if change of presence object is setting correct state."""
        # send manual off from presence
        self._presence.state_machine.set_state("presence")
        tests.helper.oh_item.send_command("Unittest_Presence", "ON", "OFF")
        self._presence._cb_presence(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Presence", "OFF", "ON"))
        self.assertEqual(self._presence.state, "absence")
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF", "ON")

        # send manual off from leaving
        self._presence.state_machine.set_state("leaving")
        tests.helper.oh_item.send_command("Unittest_Presence", "ON", "OFF")
        self._presence._cb_presence(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Presence", "OFF", "ON"))
        self.assertEqual(self._presence.state, "absence")
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF", "ON")

        # send manual on from absence
        self._presence.state_machine.set_state("absence")
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF", "ON")
        self._presence._cb_presence(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Presence", "ON", "OFF"))
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.send_command("Unittest_Presence", "ON", "OFF")

        # send manual on from long_absence
        self._presence.state_machine.set_state("long_absence")
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF", "ON")
        self._presence._cb_presence(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Presence", "ON", "OFF"))
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.send_command("Unittest_Presence", "ON", "OFF")

    def test_phones(self) -> None:
        """Test if presence is set correctly through phones."""
        # first phone switches to ON -> presence expected
        self._presence.state_machine.set_state("absence")
        tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")
        self.habapp_countdown_mock.return_value.reset.assert_not_called()

        # second phone switches to ON -> no change expected
        tests.helper.oh_item.send_command("Unittest_Phone2", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")
        self.habapp_countdown_mock.return_value.reset.assert_not_called()

        # second phone switches to OFF -> no change expected
        tests.helper.oh_item.send_command("Unittest_Phone2", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")
        self.habapp_countdown_mock.return_value.reset.assert_not_called()

        # first phone switches to OFF -> timer should be started
        tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")
        self.habapp_countdown_mock.return_value.reset.assert_called_once()
        tests.helper.timer.call_timeout(self.habapp_countdown_mock)
        self.assertEqual(self._presence.state, "leaving")

        # phone appears during leaving -> leaving expected
        self.habapp_countdown_mock.return_value.stop.reset_mock()
        tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")
        self.habapp_countdown_mock.return_value.stop.assert_called_once()

        # timeout is over -> absence expected
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "absence")
