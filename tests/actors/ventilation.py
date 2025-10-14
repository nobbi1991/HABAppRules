"""Test ventilation rules."""

import collections
import datetime
import pathlib
import sys
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.config.ventilation
import habapp_rules.actors.ventilation
import habapp_rules.core.exceptions
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer


class TestGlobalFunctions(unittest.TestCase):
    """Test global functions."""

    def test_to_datetime(self) -> None:
        """Test _to_datetime."""
        TestCase = collections.namedtuple("TestCase", "input_time, now, expected_result")

        test_cases = [
            TestCase(datetime.time(0, 0), datetime.datetime(2024, 1, 1, 0, 1), datetime.datetime(2024, 1, 2, 0, 0)),
            TestCase(datetime.time(6, 0), datetime.datetime(2024, 1, 1, 0, 1), datetime.datetime(2024, 1, 1, 6, 0)),
            TestCase(datetime.time(18, 0), datetime.datetime(2024, 1, 1, 17, 59), datetime.datetime(2024, 1, 1, 18, 0)),
            TestCase(datetime.time(18, 0), datetime.datetime(2024, 1, 1, 18, 00), datetime.datetime(2024, 1, 2, 18, 0)),
            TestCase(datetime.time(18, 0), datetime.datetime(2024, 1, 1, 18, 1), datetime.datetime(2024, 1, 2, 18, 0)),
        ]

        combine_orig = datetime.datetime.combine

        with unittest.mock.patch("datetime.datetime") as datetime_mock:
            datetime.datetime.combine = combine_orig
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    datetime_mock.now.return_value = test_case.now
                    self.assertEqual(test_case.expected_result, habapp_rules.actors.ventilation._to_datetime(test_case.input_time))


class TestVentilation(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing Ventilation."""

    def setUp(self) -> None:
        """Setup test case."""
        self.run_at_mock_patcher = unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.once")
        self.addCleanup(self.run_at_mock_patcher.stop)
        self.run_at_mock = self.run_at_mock_patcher.start()

        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_min_level", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Ventilation_min_level_state", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_max_level", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_Custom_State", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_hand_request", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_external_request", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_on", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_power", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_display_text", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", None)

        parameter_max = habapp_rules.actors.config.ventilation.VentilationParameter(
            state_normal=habapp_rules.actors.config.ventilation.StateConfig(level=101, display_text="Normal Custom"),
            state_hand=habapp_rules.actors.config.ventilation.StateConfigWithTimeout(level=102, display_text="Hand Custom", timeout=42 * 60),
            state_external=habapp_rules.actors.config.ventilation.StateConfig(level=103, display_text="External Custom"),
            state_humidity=habapp_rules.actors.config.ventilation.StateConfig(level=104, display_text="Humidity Custom"),
            state_long_absence=habapp_rules.actors.config.ventilation.StateConfigLongAbsence(level=105, display_text="Absence Custom", duration=1800, start_time=datetime.time(18)),
        )

        config_max = habapp_rules.actors.config.ventilation.VentilationConfig(
            items=habapp_rules.actors.config.ventilation.VentilationItems(
                ventilation_level="Unittest_Ventilation_max_level",
                manual="Unittest_Ventilation_max_manual",
                hand_request="Unittest_Ventilation_max_hand_request",
                external_request="Unittest_Ventilation_max_external_request",
                feedback_on="Unittest_Ventilation_max_feedback_on",
                feedback_power="Unittest_Ventilation_max_feedback_power",
                display_text="Unittest_Ventilation_max_display_text",
                presence_state="Unittest_Presence_state",
                state="Unittest_Ventilation_max_Custom_State",
            ),
            parameter=parameter_max,
        )

        config_min = habapp_rules.actors.config.ventilation.VentilationConfig(
            items=habapp_rules.actors.config.ventilation.VentilationItems(ventilation_level="Unittest_Ventilation_min_level", manual="Unittest_Ventilation_min_manual", state="H_Unittest_Ventilation_min_level_state"),
        )

        self.ventilation_min = habapp_rules.actors.ventilation.Ventilation(config_min)
        self.ventilation_max = habapp_rules.actors.ventilation.Ventilation(config_max)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "Ventilation"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
            model=tests.helper.graph_machines.FakeModel(), states=self.ventilation_min.states, transitions=self.ventilation_min.trans, initial=self.ventilation_min.state, show_conditions=False
        )

        graph.get_graph().draw(picture_dir / "Ventilation.png", format="png", prog="dot")

        for state_name in [state for state in self._get_state_names(self.ventilation_min.states) if "init" not in state.lower()]:
            graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self.ventilation_min.states, transitions=self.ventilation_min.trans, initial=state_name, show_conditions=True)
            graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Ventilation_{state_name}.png", format="png", prog="dot")

    def test_init(self) -> None:
        """Test __init__."""
        # check timeouts
        self.assertEqual(3600, self.ventilation_min.state_machine.get_state("Auto_PowerHand").timeout)
        self.assertEqual(3600, self.ventilation_min.state_machine.get_state("Auto_LongAbsence_On").timeout)

        self.assertEqual(42 * 60, self.ventilation_max.state_machine.get_state("Auto_PowerHand").timeout)
        self.assertEqual(1800, self.ventilation_max.state_machine.get_state("Auto_LongAbsence_On").timeout)

    def test_get_initial_state(self) -> None:
        """Test getting initial state."""
        TestCase = collections.namedtuple("TestCase", "presence_state, manual, hand_request, external_request, expected_state_min, expected_state_max")

        test_cases = [
            # present
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, False, False, False, "Auto_Normal", "Auto_Normal"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, False, False, True, "Auto_Normal", "Auto_PowerExternal"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, False, True, False, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, False, True, True, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, True, False, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, True, False, True, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, True, True, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, True, True, True, "Manual", "Manual"),
            # long absence
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, False, False, False, "Auto_Normal", "Auto_LongAbsence"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, False, False, True, "Auto_Normal", "Auto_LongAbsence"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, False, True, False, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, False, True, True, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, True, False, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, True, False, True, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, True, True, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, True, True, True, "Manual", "Manual"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_Ventilation_min_manual", "ON" if test_case.manual else "OFF")
                tests.helper.oh_item.set_state("Unittest_Ventilation_max_manual", "ON" if test_case.manual else "OFF")
                tests.helper.oh_item.set_state("Unittest_Ventilation_max_hand_request", "ON" if test_case.hand_request else "OFF")
                tests.helper.oh_item.set_state("Unittest_Ventilation_max_external_request", "ON" if test_case.external_request else "OFF")
                tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_state)

                self.assertEqual(test_case.expected_state_min, self.ventilation_min._get_initial_state())
                self.assertEqual(test_case.expected_state_max, self.ventilation_max._get_initial_state())

    def test_set_level(self) -> None:
        """Test _set_level."""
        TestCase = collections.namedtuple("TestCase", "state, expected_level")

        test_cases = [
            TestCase("Manual", None),
            TestCase("Auto_PowerHand", 102),
            TestCase("Auto_Normal", 101),
            TestCase("Auto_PowerExternal", 103),
            TestCase("Auto_LongAbsence_On", 105),
            TestCase("Auto_LongAbsence_Off", 0),
            TestCase("Auto_Init", None),
        ]

        with unittest.mock.patch("habapp_rules.core.helper.send_if_different") as send_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    send_mock.reset_mock()
                    self.ventilation_max.state = test_case.state

                    self.ventilation_max._set_level()

                    if test_case.expected_level is not None:
                        send_mock.assert_called_once_with(self.ventilation_max._config.items.ventilation_level, test_case.expected_level)
                    else:
                        send_mock.assert_not_called()

    def test_set_feedback_states(self) -> None:
        """Test _set_feedback_states."""
        TestCase = collections.namedtuple("TestCase", "ventilation_level, state, expected_on, expected_power, expected_display_text")

        test_cases = [
            TestCase(None, "Auto_PowerHand", False, False, "Hand Custom 42min"),
            TestCase(None, "Auto_Normal", False, False, "Normal Custom"),
            TestCase(None, "Auto_PowerExternal", False, False, "External Custom"),
            TestCase(None, "Auto_LongAbsence_On", False, False, "Absence Custom ON"),
            TestCase(None, "Auto_LongAbsence_Off", False, False, "Absence Custom OFF"),
            TestCase(None, "Auto_Init", False, False, "Absence Custom OFF"),
            TestCase(0, "Auto_PowerHand", False, False, "Hand Custom 42min"),
            TestCase(0, "Auto_Normal", False, False, "Normal Custom"),
            TestCase(0, "Auto_PowerExternal", False, False, "External Custom"),
            TestCase(0, "Auto_LongAbsence_On", False, False, "Absence Custom ON"),
            TestCase(0, "Auto_LongAbsence_Off", False, False, "Absence Custom OFF"),
            TestCase(0, "Auto_Init", False, False, "Absence Custom OFF"),
            TestCase(1, "Auto_PowerHand", True, False, "Hand Custom 42min"),
            TestCase(1, "Auto_Normal", True, False, "Normal Custom"),
            TestCase(1, "Auto_PowerExternal", True, False, "External Custom"),
            TestCase(1, "Auto_LongAbsence_On", True, False, "Absence Custom ON"),
            TestCase(1, "Auto_LongAbsence_Off", True, False, "Absence Custom OFF"),
            TestCase(1, "Auto_Init", True, False, "Absence Custom OFF"),
            TestCase(2, "Auto_PowerHand", True, True, "Hand Custom 42min"),
            TestCase(2, "Auto_Normal", True, True, "Normal Custom"),
            TestCase(2, "Auto_PowerExternal", True, True, "External Custom"),
            TestCase(2, "Auto_LongAbsence_On", True, True, "Absence Custom ON"),
            TestCase(2, "Auto_LongAbsence_Off", True, True, "Absence Custom OFF"),
            TestCase(2, "Auto_Init", True, True, "Absence Custom OFF"),
            TestCase(42, "Auto_PowerHand", True, True, "Hand Custom 42min"),
            TestCase(42, "Auto_Normal", True, True, "Normal Custom"),
            TestCase(42, "Auto_PowerExternal", True, True, "External Custom"),
            TestCase(42, "Auto_LongAbsence_On", True, True, "Absence Custom ON"),
            TestCase(42, "Auto_LongAbsence_Off", True, True, "Absence Custom OFF"),
            TestCase(42, "Auto_Init", True, True, "Absence Custom OFF"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.ventilation_min._ventilation_level = test_case.ventilation_level
                self.ventilation_max._ventilation_level = test_case.ventilation_level
                self.ventilation_min.state = test_case.state
                self.ventilation_max.state = test_case.state

                self.ventilation_min._set_feedback_states()
                self.ventilation_max._set_feedback_states()

                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_on", "ON" if test_case.expected_on else "OFF")
                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_power", "ON" if test_case.expected_power else "OFF")
                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_display_text", test_case.expected_display_text)

    def test_on_enter_long_absence_off(self) -> None:
        """Test on_enter_Auto_LongAbsence_Off."""
        with unittest.mock.patch.object(self.ventilation_max, "_trigger_long_absence_power_on") as trigger_on_mock, unittest.mock.patch("habapp_rules.actors.ventilation._to_datetime") as to_datetime_mock:
            self.ventilation_max.to_Auto_LongAbsence_Off()
        self.run_at_mock.assert_called_once_with(to_datetime_mock.return_value, trigger_on_mock)

    def test_trigger_long_absence_power_on(self) -> None:
        """Test _trigger_long_absence_power_on."""
        with unittest.mock.patch.object(self.ventilation_max, "_long_absence_power_on") as power_on_mock:
            self.ventilation_max._trigger_long_absence_power_on()
        power_on_mock.assert_called_once()

    def test__set_hand_display_text(self) -> None:
        """Test __set_hand_display_text."""
        # wrong state
        for state in ["Manual", "Auto_Normal", "Auto_PowerHumidity", "Auto_PowerDryer", "Auto_LongAbsence_On", "Auto_LongAbsence_Off"]:
            self.ventilation_max.state = state

            self.ventilation_max._VentilationBase__set_hand_display_text()
            self.run_at_mock.assert_not_called()

        # PowerHand state:
        TestCase = collections.namedtuple("TestCase", "changed_time, now_time, expected_display")

        test_cases = [
            TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 0), "Hand Custom 42min"),
            TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 0, 30), "Hand Custom 42min"),
            TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 0, 31), "Hand Custom 41min"),
            TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 2, 0), "Hand Custom 40min"),
            TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 2, 31), "Hand Custom 39min"),
            TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 42, 0), "Hand Custom 0min"),
            TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 45, 0), "Hand Custom 0min"),
        ]

        self.ventilation_max.state = "Auto_PowerHand"

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.ventilation_max._state_change_time = test_case.changed_time
                now_value = test_case.now_time
                self.run_at_mock.reset_mock()
                with unittest.mock.patch("datetime.datetime") as datetime_mock:
                    datetime_mock.now.return_value = now_value
                    self.ventilation_max._VentilationBase__set_hand_display_text()
                self.run_at_mock.assert_called_once()
                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_display_text", test_case.expected_display)

    def test_external_active_and_configured(self) -> None:
        """Test _external_active_and_configured."""
        self.assertFalse(self.ventilation_min._external_active_and_configured())

        tests.helper.oh_item.set_state("Unittest_Ventilation_max_external_request", "OFF")
        self.assertFalse(self.ventilation_max._external_active_and_configured())

        tests.helper.oh_item.set_state("Unittest_Ventilation_max_external_request", "ON")
        self.assertTrue(self.ventilation_max._external_active_and_configured())

    def test_auto_normal_transitions(self) -> None:
        """Test transitions of state Auto_Normal."""
        # to Auto_PowerHand
        self.ventilation_min.to_Auto_Normal()
        self.ventilation_max.to_Auto_Normal()

        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

        # back to Auto_Normal
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

        # to Auto_PowerExternal
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

        # back to Auto_Normal
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "OFF")

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

        # to Auto_LongAbsence
        tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", habapp_rules.system.PresenceState.LONG_ABSENCE.value)

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_LongAbsence_Off", self.ventilation_max.state)

        # back to Auto_Normal
        tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

    def test_auto_power_external_transitions(self) -> None:
        """Test transitions of state Auto_PowerExternal."""
        # to Auto_PowerExternal
        self.ventilation_max.to_Auto_PowerExternal()
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "OFF")
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

        # back to AutoPowerExternal
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
        self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

        # to Auto_PowerHand
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
        self.assertEqual("Auto_PowerHand", self.ventilation_max.state)
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
        self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

        # back to AutoPowerExternal
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")
        self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

        # to Auto_LongAbsence
        tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", habapp_rules.system.PresenceState.LONG_ABSENCE.value)
        self.assertEqual("Auto_LongAbsence_Off", self.ventilation_max.state)

    def test_auto_power_hand_transitions(self) -> None:
        """Test transitions of state Auto_PowerHand."""
        # set Auto_LongAbsence as initial state
        self.ventilation_max.to_Auto_LongAbsence_On()

        # to Auto_PowerHand
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
        self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

        # to Auto_Normal (external request is not ON)
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

        # back to Auto_PowerHand
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
        self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

        # to Auto_PowerExternal
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")
        self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

        # back to Auto_PowerHand
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
        self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

        # timeout
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "OFF")
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_hand_request", "OFF")

    def test_manual_transitions(self) -> None:
        """Test transitions of state Manual."""
        # set Auto as initial state
        self.ventilation_min.to_Auto_Normal()
        self.ventilation_max.to_Auto_Normal()

        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_min_manual", "ON")
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_manual", "ON")

        self.assertEqual("Manual", self.ventilation_min.state)
        self.assertEqual("Manual", self.ventilation_max.state)

        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_min_manual", "OFF")
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_manual", "OFF")

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)


class TestVentilationHeliosTwoStage(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing VentilationHeliosTwoStage."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_output_on", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_output_power", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Ventilation_min_output_on_state", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_output_on", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_output_power", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_Custom_State", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_hand_request", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_external_request", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_on", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_power", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_max_feedback_ventilation_level", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_display_text", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", None)

        parameter_max = habapp_rules.actors.config.ventilation.VentilationTwoStageParameter(
            state_normal=habapp_rules.actors.config.ventilation.StateConfig(level=101, display_text="Normal Custom"),
            state_hand=habapp_rules.actors.config.ventilation.StateConfigWithTimeout(level=102, display_text="Hand Custom", timeout=42 * 60),
            state_external=habapp_rules.actors.config.ventilation.StateConfig(level=103, display_text="External Custom"),
            state_humidity=habapp_rules.actors.config.ventilation.StateConfig(level=104, display_text="Humidity Custom"),
            state_long_absence=habapp_rules.actors.config.ventilation.StateConfigLongAbsence(level=105, display_text="Absence Custom", duration=1800, start_time=datetime.time(18)),
            state_after_run=habapp_rules.actors.config.ventilation.StateConfig(level=99, display_text="AfterRun Custom"),
            after_run_timeout=350,
        )

        config_max = habapp_rules.actors.config.ventilation.VentilationTwoStageConfig(
            items=habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
                ventilation_output_on="Unittest_Ventilation_max_output_on",
                ventilation_output_power="Unittest_Ventilation_max_output_power",
                manual="Unittest_Ventilation_max_manual",
                hand_request="Unittest_Ventilation_max_hand_request",
                external_request="Unittest_Ventilation_max_external_request",
                feedback_on="Unittest_Ventilation_max_feedback_on",
                feedback_power="Unittest_Ventilation_max_feedback_power",
                display_text="Unittest_Ventilation_max_display_text",
                presence_state="Unittest_Presence_state",
                state="Unittest_Ventilation_max_Custom_State",
                feedback_ventilation_level="Unittest_Ventilation_max_feedback_ventilation_level",
            ),
            parameter=parameter_max,
        )

        config_min = habapp_rules.actors.config.ventilation.VentilationTwoStageConfig(
            items=habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
                ventilation_output_on="Unittest_Ventilation_min_output_on", ventilation_output_power="Unittest_Ventilation_min_output_power", manual="Unittest_Ventilation_min_manual", state="H_Unittest_Ventilation_min_output_on_state"
            )
        )

        self.ventilation_min = habapp_rules.actors.ventilation.VentilationHeliosTwoStage(config_min)
        self.ventilation_max = habapp_rules.actors.ventilation.VentilationHeliosTwoStage(config_max)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "VentilationHeliosTwoStage"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
            model=tests.helper.graph_machines.FakeModel(), states=self.ventilation_min.states, transitions=self.ventilation_min.trans, initial=self.ventilation_min.state, show_conditions=False
        )

        graph.get_graph().draw(picture_dir / "Ventilation.png", format="png", prog="dot")

        for state_name in [state for state in self._get_state_names(self.ventilation_min.states) if "init" not in state.lower()]:
            graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self.ventilation_min.states, transitions=self.ventilation_min.trans, initial=state_name, show_conditions=True)
            graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Ventilation_{state_name}.png", format="png", prog="dot")

    def test_set_level(self) -> None:
        """Test _set_level."""
        TestCase = collections.namedtuple("TestCase", "state, expected_on, expected_power, expected_level")

        test_cases = [
            TestCase("Manual", None, None, 101),
            TestCase("Auto_PowerHand", "ON", "ON", 102),
            TestCase("Auto_Normal", "ON", "OFF", 1),
            TestCase("Auto_PowerExternal", "ON", "ON", 103),
            TestCase("Auto_LongAbsence_On", "ON", "ON", 105),
            TestCase("Auto_LongAbsence_Off", "OFF", "OFF", 0),
            TestCase("Auto_Init", None, None, 0),
            TestCase("Auto_PowerAfterRun", "ON", "OFF", 99),
        ]

        self.ventilation_max._config.parameter.state_normal.level = 1

        with unittest.mock.patch("habapp_rules.core.helper.send_if_different") as send_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    send_mock.reset_mock()
                    self.ventilation_max.state = test_case.state

                    self.ventilation_max._set_level()

                    if test_case.expected_on is not None:
                        send_mock.assert_any_call(self.ventilation_max._config.items.ventilation_output_on, test_case.expected_on)

                    if test_case.expected_power is not None:
                        send_mock.assert_any_call(self.ventilation_max._config.items.ventilation_output_power, test_case.expected_power)

                    tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_ventilation_level", test_case.expected_level)

    def test_set_feedback_states(self) -> None:
        """Test _set_feedback_states."""
        TestCase = collections.namedtuple("TestCase", "ventilation_level, state, expected_on, expected_power, expected_display_text")

        test_cases = [TestCase(None, "Auto_PowerAfterRun", False, False, "AfterRun Custom"), TestCase(0, "Auto_PowerAfterRun", False, False, "AfterRun Custom"), TestCase(1, "Auto_PowerAfterRun", True, False, "AfterRun Custom")]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.ventilation_min._ventilation_level = test_case.ventilation_level
                self.ventilation_max._ventilation_level = test_case.ventilation_level
                self.ventilation_min.state = test_case.state
                self.ventilation_max.state = test_case.state

                self.ventilation_min._set_feedback_states()
                self.ventilation_max._set_feedback_states()

                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_on", "ON" if test_case.expected_on else "OFF")
                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_power", "ON" if test_case.expected_power else "OFF")
                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_display_text", test_case.expected_display_text)

    def test_power_after_run_transitions(self) -> None:
        """Test transitions of PowerAfterRun."""
        # PowerAfterRun to PowerHand
        self.ventilation_max.to_Auto_PowerAfterRun()
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
        self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

        # back to PowerAfterRun
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")
        self.assertEqual("Auto_PowerAfterRun", self.ventilation_max.state)

        # PowerAfterRun to PowerExternal
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
        self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

        # back to PowerAfterRun
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "OFF")
        self.assertEqual("Auto_PowerAfterRun", self.ventilation_max.state)

        # timeout of PowerAfterRun
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)


class TestVentilationHeliosTwoStageHumidity(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing VentilationHeliosTwoStageHumidity."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_output_on", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_output_power", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_min_current", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Ventilation_min_output_on_state", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_output_on", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_output_power", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_max_current", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_Custom_State", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_hand_request", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_external_request", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_on", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_power", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_display_text", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", None)

        parameter_max = habapp_rules.actors.config.ventilation.VentilationTwoStageParameter(
            state_normal=habapp_rules.actors.config.ventilation.StateConfig(level=101, display_text="Normal Custom"),
            state_hand=habapp_rules.actors.config.ventilation.StateConfigWithTimeout(level=102, display_text="Hand Custom", timeout=42 * 60),
            state_external=habapp_rules.actors.config.ventilation.StateConfig(level=103, display_text="External Custom"),
            state_humidity=habapp_rules.actors.config.ventilation.StateConfig(level=104, display_text="Humidity Custom"),
            state_long_absence=habapp_rules.actors.config.ventilation.StateConfigLongAbsence(level=105, display_text="Absence Custom", duration=1800, start_time=datetime.time(18)),
            after_run_timeout=350,
            current_threshold_power=0.5,
        )

        config_max = habapp_rules.actors.config.ventilation.VentilationTwoStageConfig(
            items=habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
                ventilation_output_on="Unittest_Ventilation_max_output_on",
                ventilation_output_power="Unittest_Ventilation_max_output_power",
                current="Unittest_Ventilation_max_current",
                manual="Unittest_Ventilation_max_manual",
                hand_request="Unittest_Ventilation_max_hand_request",
                external_request="Unittest_Ventilation_max_external_request",
                feedback_on="Unittest_Ventilation_max_feedback_on",
                feedback_power="Unittest_Ventilation_max_feedback_power",
                display_text="Unittest_Ventilation_max_display_text",
                presence_state="Unittest_Presence_state",
                state="Unittest_Ventilation_max_Custom_State",
            ),
            parameter=parameter_max,
        )

        config_min = habapp_rules.actors.config.ventilation.VentilationTwoStageConfig(
            items=habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
                ventilation_output_on="Unittest_Ventilation_min_output_on",
                ventilation_output_power="Unittest_Ventilation_min_output_power",
                current="Unittest_Ventilation_min_current",
                manual="Unittest_Ventilation_min_manual",
                state="H_Unittest_Ventilation_min_output_on_state",
            )
        )

        self.ventilation_min = habapp_rules.actors.ventilation.VentilationHeliosTwoStageHumidity(config_min)
        self.ventilation_max = habapp_rules.actors.ventilation.VentilationHeliosTwoStageHumidity(config_max)

    def test_init_without_current_item(self) -> None:
        """Test __init__ without current item."""
        config = habapp_rules.actors.config.ventilation.VentilationTwoStageConfig(
            items=habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
                ventilation_output_on="Unittest_Ventilation_min_output_on", ventilation_output_power="Unittest_Ventilation_min_output_power", manual="Unittest_Ventilation_min_manual", state="H_Unittest_Ventilation_min_output_on_state"
            )
        )
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.actors.ventilation.VentilationHeliosTwoStageHumidity(config)

    def test_set_level(self) -> None:
        """Test _set_level."""
        TestCase = collections.namedtuple("TestCase", "state, expected_on, expected_power")

        test_cases = [
            TestCase("Manual", None, None),
            TestCase("Auto_PowerHand", "ON", "ON"),
            TestCase("Auto_Normal", "ON", "OFF"),
            TestCase("Auto_PowerExternal", "ON", "ON"),
            TestCase("Auto_LongAbsence_On", "ON", "ON"),
            TestCase("Auto_LongAbsence_Off", "OFF", "OFF"),
            TestCase("Auto_Init", None, None),
            TestCase("Auto_PowerAfterRun", "ON", "OFF"),
            TestCase("Auto_PowerHumidity", "ON", "OFF"),
        ]

        self.ventilation_max._config.parameter.state_normal.level = 1

        with unittest.mock.patch("habapp_rules.core.helper.send_if_different") as send_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    send_mock.reset_mock()
                    self.ventilation_max.state = test_case.state

                    self.ventilation_max._set_level()

                    if test_case.expected_on is not None:
                        send_mock.assert_any_call(self.ventilation_max._config.items.ventilation_output_on, test_case.expected_on)

                    if test_case.expected_power is not None:
                        send_mock.assert_any_call(self.ventilation_max._config.items.ventilation_output_power, test_case.expected_power)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "VentilationHeliosTwoStageHumidity"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
            model=tests.helper.graph_machines.FakeModel(), states=self.ventilation_min.states, transitions=self.ventilation_min.trans, initial=self.ventilation_min.state, show_conditions=False
        )

        graph.get_graph().draw(picture_dir / "Ventilation.png", format="png", prog="dot")

        for state_name in [state for state in self._get_state_names(self.ventilation_min.states) if "init" not in state.lower()]:
            graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self.ventilation_min.states, transitions=self.ventilation_min.trans, initial=state_name, show_conditions=True)
            graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Ventilation_{state_name}.png", format="png", prog="dot")

    def test_get_initial_state(self) -> None:
        """Test _get_initial_state."""
        TestCase = collections.namedtuple("TestCase", "presence_state, current, manual, hand_request, external_request, expected_state_min, expected_state_max")

        test_cases = [
            # present | current = None
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, False, False, False, "Auto_Normal", "Auto_Normal"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, False, False, True, "Auto_Normal", "Auto_PowerExternal"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, False, True, False, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, False, True, True, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, True, False, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, True, False, True, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, True, True, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, True, True, True, "Manual", "Manual"),
            # present | current smaller than the threshold
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, False, False, False, "Auto_Normal", "Auto_Normal"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, False, False, True, "Auto_Normal", "Auto_PowerExternal"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, False, True, False, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, False, True, True, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, True, False, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, True, False, True, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, True, True, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, True, True, True, "Manual", "Manual"),
            # present | current greater than the threshold
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, False, False, False, "Auto_Normal", "Auto_PowerHumidity"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, False, False, True, "Auto_Normal", "Auto_PowerExternal"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, False, True, False, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, False, True, True, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, True, False, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, True, False, True, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, True, True, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, True, True, True, "Manual", "Manual"),
            # long absence
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, False, False, False, "Auto_Normal", "Auto_LongAbsence"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, False, False, True, "Auto_Normal", "Auto_LongAbsence"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, False, True, False, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, False, True, True, "Auto_Normal", "Auto_PowerHand"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, True, False, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, True, False, True, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, True, True, False, "Manual", "Manual"),
            TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, True, True, True, "Manual", "Manual"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_Ventilation_min_manual", "ON" if test_case.manual else "OFF")
                tests.helper.oh_item.set_state("Unittest_Ventilation_max_manual", "ON" if test_case.manual else "OFF")
                tests.helper.oh_item.set_state("Unittest_Ventilation_max_current", test_case.current)
                tests.helper.oh_item.set_state("Unittest_Ventilation_max_hand_request", "ON" if test_case.hand_request else "OFF")
                tests.helper.oh_item.set_state("Unittest_Ventilation_max_external_request", "ON" if test_case.external_request else "OFF")
                tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_state)

                self.assertEqual(test_case.expected_state_min, self.ventilation_min._get_initial_state())
                self.assertEqual(test_case.expected_state_max, self.ventilation_max._get_initial_state())

    def test_set_feedback_states(self) -> None:
        """Test _set_feedback_states."""
        TestCase = collections.namedtuple("TestCase", "ventilation_level, state, expected_on, expected_power, expected_display_text")

        test_cases = [
            TestCase(None, "Auto_PowerHumidity", False, False, "Humidity Custom"),
            TestCase(0, "Auto_PowerHumidity", False, False, "Humidity Custom"),
            TestCase(1, "Auto_PowerHumidity", True, False, "Humidity Custom"),
            TestCase(2, "Auto_PowerHumidity", True, True, "Humidity Custom"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.ventilation_min._ventilation_level = test_case.ventilation_level
                self.ventilation_max._ventilation_level = test_case.ventilation_level
                self.ventilation_min.state = test_case.state
                self.ventilation_max.state = test_case.state

                self.ventilation_min._set_feedback_states()
                self.ventilation_max._set_feedback_states()

                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_on", "ON" if test_case.expected_on else "OFF")
                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_power", "ON" if test_case.expected_power else "OFF")
                tests.helper.oh_item.assert_value("Unittest_Ventilation_max_display_text", test_case.expected_display_text)

    def test_current_greater_threshold(self) -> None:
        """Test __current_greater_threshold."""
        TestCase = collections.namedtuple("TestCase", "threshold, item_value, given_value, expected_result")

        test_cases = [TestCase(42, 0, 0, False), TestCase(42, 0, 100, True), TestCase(42, 100, 0, False), TestCase(42, 100, 100, True), TestCase(42, 0, None, False), TestCase(42, 100, None, True), TestCase(42, None, None, False)]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.ventilation_max._current_threshold_power = test_case.threshold
                tests.helper.oh_item.set_state("Unittest_Ventilation_max_current", test_case.item_value)

                result = self.ventilation_max._current_greater_threshold() if test_case.given_value is None else self.ventilation_max._current_greater_threshold(test_case.given_value)

                self.assertEqual(test_case.expected_result, result)

    def test_power_after_run_transitions(self) -> None:
        """Test transitions of PowerAfterRun."""
        # _end_after_run triggered
        self.ventilation_max.to_Auto_PowerAfterRun()
        self.ventilation_max._end_after_run()
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

    def test_power_humidity_transitions(self) -> None:
        """Test transitions of state Auto_PowerHumidity."""
        # set default config parameters
        self.ventilation_min._config.parameter = habapp_rules.actors.config.ventilation.VentilationTwoStageParameter()
        self.ventilation_max._config.parameter = habapp_rules.actors.config.ventilation.VentilationTwoStageParameter()

        # set AutoNormal as initial state
        self.ventilation_min.to_Auto_Normal()
        self.ventilation_max.to_Auto_Normal()

        # set correct output states
        self.ventilation_min._config.items.ventilation_output_power.set_value("OFF")
        self.ventilation_max._config.items.ventilation_output_power.set_value("OFF")

        # state != Auto_PowerHumidity | current below the threshold
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.1)
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.1)

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

        tests.helper.oh_item.assert_value("Unittest_Ventilation_min_output_on", "ON")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_min_output_power", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_on", "ON")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_power", "OFF")

        # state != Auto_PowerHumidity | current grater then the threshold
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.2)
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.6)

        self.assertEqual("Auto_PowerHumidity", self.ventilation_min.state)
        self.assertEqual("Auto_PowerHumidity", self.ventilation_max.state)

        tests.helper.oh_item.assert_value("Unittest_Ventilation_min_output_on", "ON")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_min_output_power", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_on", "ON")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_power", "OFF")

        # state == Auto_PowerHumidity | current grater then the threshold
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.2)
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.6)

        self.assertEqual("Auto_PowerHumidity", self.ventilation_min.state)
        self.assertEqual("Auto_PowerHumidity", self.ventilation_max.state)

        # state == Auto_PowerHumidity | current below then the threshold
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.1)
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.1)

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

        # state == Auto_PowerAfterRun | current below the threshold
        self.ventilation_min.to_Auto_PowerAfterRun()
        self.ventilation_max.to_Auto_PowerAfterRun()

        tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.1)
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.1)

        self.ventilation_min._after_run_timeout()
        self.ventilation_max._after_run_timeout()

        self.assertEqual("Auto_Normal", self.ventilation_min.state)
        self.assertEqual("Auto_Normal", self.ventilation_max.state)

        # state == Auto_PowerAfterRun | current grater then the threshold
        self.ventilation_min.to_Auto_PowerAfterRun()
        self.ventilation_max.to_Auto_PowerAfterRun()

        tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.2)
        tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.6)

        self.ventilation_min._after_run_timeout()
        self.ventilation_max._after_run_timeout()

        self.assertEqual("Auto_PowerHumidity", self.ventilation_min.state)
        self.assertEqual("Auto_PowerHumidity", self.ventilation_max.state)

        tests.helper.oh_item.assert_value("Unittest_Ventilation_min_output_on", "ON")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_min_output_power", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_on", "ON")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_power", "OFF")

        # state == Auto_PowerHumidity | _hand_on triggered
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
        self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_on", "ON")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_power", "ON")

        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")

        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_on", "ON")
        tests.helper.oh_item.assert_value("Unittest_Ventilation_max_output_power", "OFF")

        # state == Auto_PowerHumidity | _external_on triggered
        self.ventilation_max.to_Auto_PowerHumidity()
        tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
        self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)
