"""Test energy save switch rules."""

import collections
import pathlib
import sys
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.config.energy_save_switch
import habapp_rules.actors.energy_save_switch
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer
from habapp_rules.system import PresenceState, SleepState


class TestEnergySaveSwitch(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing energy save switch."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Min_Switch")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Min_State")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Max_Switch")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Max_State")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Max_Manual")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_External_Request")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Current_Switch")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Current_State")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Current_Manual")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Current")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state")

        self._config_min = habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchConfig(items=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchItems(switch="Unittest_Min_Switch", state="Unittest_Min_State"))

        self._config_max_without_current = habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchConfig(
            items=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchItems(
                switch="Unittest_Max_Switch", state="Unittest_Max_State", manual="Unittest_Max_Manual", external_request="Unittest_External_Request", presence_state="Unittest_Presence_state", sleeping_state="Unittest_Sleep_state"
            ),
            parameter=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchParameter(max_on_time=3600, hand_timeout=1800),
        )

        self._config_current = habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchConfig(
            items=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchItems(
                switch="Unittest_Current_Switch", state="Unittest_Current_State", manual="Unittest_Current_Manual", current="Unittest_Current", presence_state="Unittest_Presence_state", sleeping_state="Unittest_Sleep_state"
            ),
            parameter=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchParameter(current_threshold=0.1, extended_wait_for_current_time=142),
        )

        self._rule_min = habapp_rules.actors.energy_save_switch.EnergySaveSwitch(self._config_min)
        self._rule_max_without_current = habapp_rules.actors.energy_save_switch.EnergySaveSwitch(self._config_max_without_current)
        self._rule_with_current = habapp_rules.actors.energy_save_switch.EnergySaveSwitch(self._config_current)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "EnergySaveSwitch"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self._rule_min.states, transitions=self._rule_min.trans, initial=self._rule_min.state, show_conditions=False)

        graph.get_graph().draw(picture_dir / "EnergySaveSwitch.png", format="png", prog="dot")

        for state_name in [state for state in self._get_state_names(self._rule_min.states) if "init" not in state.lower()]:
            graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self._rule_min.states, transitions=self._rule_min.trans, initial=state_name, show_conditions=True)
            graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"EnergySaveSwitch_{state_name}.png", format="png", prog="dot")

    def test_set_timeout(self) -> None:
        """Test set timeout."""
        self.assertEqual(self._rule_min.state_machine.states["Hand"].timeout, 0)
        self.assertEqual(self._rule_max_without_current.state_machine.states["Hand"].timeout, 1800)
        self.assertEqual(self._rule_with_current.state_machine.states["Hand"].timeout, 0)

        self.assertEqual(self._rule_min.state_machine.states["Auto"].states["WaitCurrentExtended"].timeout, 60)
        self.assertEqual(self._rule_max_without_current.state_machine.states["Auto"].states["WaitCurrentExtended"].timeout, 60)
        self.assertEqual(self._rule_with_current.state_machine.states["Auto"].states["WaitCurrentExtended"].timeout, 142)

    def test_get_initial_state(self) -> None:
        """Test get initial state."""
        TestCase = collections.namedtuple("TestCase", "current_above_threshold, manual, on_conditions_met, expected_state")

        test_cases = [
            # current below threshold
            TestCase(current_above_threshold=False, manual=None, on_conditions_met=False, expected_state="Auto_Off"),
            TestCase(current_above_threshold=False, manual=None, on_conditions_met=True, expected_state="Auto_On"),
            TestCase(current_above_threshold=False, manual=False, on_conditions_met=False, expected_state="Auto_Off"),
            TestCase(current_above_threshold=False, manual=False, on_conditions_met=True, expected_state="Auto_On"),
            TestCase(current_above_threshold=False, manual=True, on_conditions_met=False, expected_state="Manual"),
            TestCase(current_above_threshold=False, manual=True, on_conditions_met=True, expected_state="Manual"),
            # current above threshold
            TestCase(current_above_threshold=True, manual=None, on_conditions_met=False, expected_state="Auto_WaitCurrent"),
            TestCase(current_above_threshold=True, manual=None, on_conditions_met=True, expected_state="Auto_On"),
            TestCase(current_above_threshold=True, manual=False, on_conditions_met=False, expected_state="Auto_WaitCurrent"),
            TestCase(current_above_threshold=True, manual=False, on_conditions_met=True, expected_state="Auto_On"),
            TestCase(current_above_threshold=True, manual=True, on_conditions_met=False, expected_state="Manual"),
            TestCase(current_above_threshold=True, manual=True, on_conditions_met=True, expected_state="Manual"),
        ]

        with unittest.mock.patch.object(self._rule_max_without_current, "_get_on_off_conditions_met") as on_conditions_mock, unittest.mock.patch.object(self._rule_max_without_current, "_current_above_threshold") as current_above_threshold_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    on_conditions_mock.return_value = test_case.on_conditions_met
                    current_above_threshold_mock.return_value = test_case.current_above_threshold

                    if test_case.manual is None:
                        self._rule_max_without_current._config.items.manual = None
                    else:
                        self._rule_max_without_current._config.items.manual = unittest.mock.MagicMock()
                        self._rule_max_without_current._config.items.manual.is_on.return_value = test_case.manual

                    self.assertEqual(test_case.expected_state, self._rule_max_without_current._get_initial_state())

    def test_current_above_threshold(self) -> None:
        """Test current above threshold."""
        TestCase = collections.namedtuple("TestCase", "current, threshold, expected_result")

        test_cases = [
            TestCase(current=None, threshold=0.1, expected_result=False),
            TestCase(current=None, threshold=0.1, expected_result=False),
            TestCase(current=None, threshold=0.1, expected_result=False),
            TestCase(current=0.0, threshold=0.1, expected_result=False),
            TestCase(current=0.1, threshold=0.1, expected_result=False),
            TestCase(current=0.2, threshold=0.1, expected_result=True),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                if test_case.current is None:
                    self._rule_with_current._config.items.current = None
                else:
                    self._rule_with_current._config.items.current = unittest.mock.MagicMock(value=test_case.current)

                self._rule_with_current._config.parameter.current_threshold = test_case.threshold
                self.assertEqual(test_case.expected_result, self._rule_with_current._current_above_threshold())

    def test_auto_off_transitions(self) -> None:
        """Test auto off transitions."""
        TestCase = collections.namedtuple("TestCase", "external_req, sleeping_state, presence_state, expected_state")
        test_cases = [
            TestCase(external_req="OFF", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.ABSENCE, expected_state="Auto_Off"),
            TestCase(external_req="OFF", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.PRESENCE, expected_state="Auto_Off"),
            TestCase(external_req="OFF", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.ABSENCE, expected_state="Auto_Off"),
            TestCase(external_req="OFF", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.PRESENCE, expected_state="Auto_On"),
            TestCase(external_req="ON", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.ABSENCE, expected_state="Auto_On"),
            TestCase(external_req="ON", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.PRESENCE, expected_state="Auto_On"),
            TestCase(external_req="ON", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.ABSENCE, expected_state="Auto_On"),
            TestCase(external_req="ON", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.PRESENCE, expected_state="Auto_On"),
        ]

        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Min_State", "Auto_Off")

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.item_state_change_event("Unittest_External_Request", test_case.external_req)
                tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", test_case.sleeping_state.value)
                tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", test_case.presence_state.value)

                tests.helper.oh_item.assert_value("Unittest_Max_State", test_case.expected_state)
                tests.helper.oh_item.assert_value("Unittest_Max_Switch", "ON" if test_case.expected_state == "Auto_On" else "OFF")

                tests.helper.oh_item.assert_value("Unittest_Min_State", "Auto_Off")

    def test_auto_on_transitions(self) -> None:
        """Test auto on transitions."""
        # max on time
        self._rule_min.to_Auto_On()
        self._rule_max_without_current.to_Auto_On()
        self._rule_with_current.to_Auto_On()

        self.assertIsNone(self._rule_min._max_on_countdown)
        self.assertIsNotNone(self._rule_max_without_current._max_on_countdown)
        self.assertIsNone(self._rule_with_current._max_on_countdown)

        self._rule_min._cb_max_on_countdown()
        self._rule_max_without_current._cb_max_on_countdown()
        self._rule_with_current._cb_max_on_countdown()

        tests.helper.oh_item.assert_value("Unittest_Min_State", "Auto_On")
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_On")

        # off conditions met
        TestCase = collections.namedtuple("TestCase", "current_above_threshold, external_req, sleeping_state, presence_state, expected_state_max, expected_state_current")
        test_cases = [
            TestCase(current_above_threshold=False, external_req="OFF", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.ABSENCE, expected_state_max="Auto_Off", expected_state_current="Auto_Off"),
            TestCase(current_above_threshold=False, external_req="OFF", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.PRESENCE, expected_state_max="Auto_Off", expected_state_current="Auto_Off"),
            TestCase(current_above_threshold=False, external_req="OFF", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.ABSENCE, expected_state_max="Auto_Off", expected_state_current="Auto_Off"),
            TestCase(current_above_threshold=False, external_req="OFF", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.PRESENCE, expected_state_max="Auto_On", expected_state_current="Auto_On"),
            TestCase(current_above_threshold=False, external_req="ON", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.ABSENCE, expected_state_max="Auto_On", expected_state_current="Auto_Off"),
            TestCase(current_above_threshold=False, external_req="ON", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.PRESENCE, expected_state_max="Auto_On", expected_state_current="Auto_Off"),
            TestCase(current_above_threshold=False, external_req="ON", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.ABSENCE, expected_state_max="Auto_On", expected_state_current="Auto_Off"),
            TestCase(current_above_threshold=False, external_req="ON", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.PRESENCE, expected_state_max="Auto_On", expected_state_current="Auto_On"),
            TestCase(current_above_threshold=True, external_req="OFF", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.ABSENCE, expected_state_max="Auto_Off", expected_state_current="Auto_WaitCurrent"),
            TestCase(current_above_threshold=True, external_req="OFF", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.PRESENCE, expected_state_max="Auto_Off", expected_state_current="Auto_WaitCurrent"),
            TestCase(current_above_threshold=True, external_req="OFF", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.ABSENCE, expected_state_max="Auto_Off", expected_state_current="Auto_WaitCurrent"),
            TestCase(current_above_threshold=True, external_req="OFF", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.PRESENCE, expected_state_max="Auto_On", expected_state_current="Auto_On"),
            TestCase(current_above_threshold=True, external_req="ON", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.ABSENCE, expected_state_max="Auto_On", expected_state_current="Auto_WaitCurrent"),
            TestCase(current_above_threshold=True, external_req="ON", sleeping_state=SleepState.SLEEPING, presence_state=PresenceState.PRESENCE, expected_state_max="Auto_On", expected_state_current="Auto_WaitCurrent"),
            TestCase(current_above_threshold=True, external_req="ON", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.ABSENCE, expected_state_max="Auto_On", expected_state_current="Auto_WaitCurrent"),
            TestCase(current_above_threshold=True, external_req="ON", sleeping_state=SleepState.AWAKE, presence_state=PresenceState.PRESENCE, expected_state_max="Auto_On", expected_state_current="Auto_On"),
        ]

        with unittest.mock.patch.object(self._rule_with_current, "_current_above_threshold", return_value=None) as mock_current_above_threshold:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    mock_current_above_threshold.return_value = test_case.current_above_threshold
                    self._rule_min.to_Auto_On()
                    self._rule_max_without_current.to_Auto_On()
                    self._rule_with_current.to_Auto_On()

                    tests.helper.oh_item.item_state_change_event("Unittest_External_Request", test_case.external_req)
                    tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", test_case.sleeping_state.value)
                    tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", test_case.presence_state.value)

                    tests.helper.oh_item.assert_value("Unittest_Max_State", test_case.expected_state_max)
                    tests.helper.oh_item.assert_value("Unittest_Max_Switch", "ON" if test_case.expected_state_max == "Auto_On" else "OFF")

                    tests.helper.oh_item.assert_value("Unittest_Current_State", test_case.expected_state_current)
                    tests.helper.oh_item.assert_value("Unittest_Current_Switch", "ON" if test_case.expected_state_current in {"Auto_On", "Auto_WaitCurrent"} else "OFF")

                    tests.helper.oh_item.assert_value("Unittest_Min_State", "Auto_On")

    def test_auto_on_transitions_timeout(self) -> None:
        """Test auto on transitions with max_on_countdown."""
        # external request OFF
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "OFF")
        self._rule_max_without_current.to_Auto_On()
        self._rule_max_without_current._cb_max_on_countdown()
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "OFF")

        # external request ON
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "ON")
        self._rule_max_without_current.to_Auto_On()
        self._rule_max_without_current._cb_max_on_countdown()
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_On")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "ON")
        # external to off
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "OFF")

    def test_auto_wait_current_transitions(self) -> None:
        """Test Auto_WaitCurrent transitions."""
        # on conditions met
        self._rule_with_current.to_Auto_WaitCurrent()
        self._rule_with_current.on_conditions_met()
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_On")
        tests.helper.oh_item.assert_value("Unittest_Current_Switch", "ON")

        # current below threshold
        self._rule_with_current.to_Auto_WaitCurrent()
        self._rule_with_current.current_below_threshold()
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_WaitCurrentExtended")
        tests.helper.oh_item.assert_value("Unittest_Current_Switch", "ON")

        # max_on_countdown | external request off
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "OFF")
        self._rule_max_without_current.to_Auto_WaitCurrent()
        self._rule_max_without_current._cb_max_on_countdown()
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "OFF")

        # max_on_countdown | external request on
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "ON")
        self._rule_max_without_current.to_Auto_WaitCurrent()
        self._rule_max_without_current._cb_max_on_countdown()
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_WaitCurrent")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "ON")
        # external to off
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "OFF")

    def test_hand_transitions(self) -> None:
        """Test Hand transitions."""
        # max_on_countdown | external request off
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "OFF")
        self._rule_max_without_current.to_Hand()
        self._rule_max_without_current._cb_max_on_countdown()
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "OFF")

        # max_on_countdown | external request on
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "ON")
        self._rule_max_without_current.to_Hand()
        self._rule_max_without_current._cb_max_on_countdown()
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Hand")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "ON")
        # external to off
        tests.helper.oh_item.item_state_change_event("Unittest_External_Request", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Max_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Max_Switch", "OFF")

        # hand timeout
        self._rule_max_without_current.to_Hand()
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_Off")
        tests.helper.oh_item.assert_value("Unittest_Current_Switch", "OFF")

        # manual off
        self._rule_max_without_current.to_Hand()
        tests.helper.oh_item.item_state_change_event("Unittest_Current_Manual", "ON")
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Manual")
        tests.helper.oh_item.assert_value("Unittest_Current_Switch", "OFF")

    def test_to_hand_transitions(self) -> None:
        """Test to Hand transitions."""
        for state in ["Auto_On", "Auto_WaitCurrent", "Auto_Off"]:
            with self.subTest(state=state):
                eval(f"self._rule_with_current.to_{state}()")  # noqa: S307
                tests.helper.oh_item.item_state_change_event("Unittest_Current_Switch", "OFF")
                tests.helper.oh_item.item_state_change_event("Unittest_Current_Switch", "ON")
                tests.helper.oh_item.assert_value("Unittest_Current_State", "Hand")

    def test_manual_transitions(self) -> None:
        """Test Manual transitions."""
        # manual off | on_off_conditions not met
        self._rule_with_current.to_Manual()
        tests.helper.oh_item.item_state_change_event("Unittest_Current_Manual", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_Off")

        # manual off | on_off_conditions met
        self._rule_with_current.to_Manual()
        tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", PresenceState.PRESENCE.value)
        tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", SleepState.AWAKE.value)
        tests.helper.oh_item.item_state_change_event("Unittest_Current_Manual", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_On")

    def test_wait_current_extended_transitions(self) -> None:
        """Test WaitCurrentExtended transitions."""
        # on conditions met
        self._rule_with_current.to_Auto_WaitCurrentExtended()
        self._rule_with_current.on_conditions_met()
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_On")

        # current above threshold
        self._rule_with_current.to_Auto_WaitCurrentExtended()
        tests.helper.oh_item.send_command("Unittest_Current", 2)
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_WaitCurrent")

        # extended timeout
        self._rule_with_current.to_Auto_WaitCurrentExtended()
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_Off")

    def test_current_switch_off(self) -> None:
        """Test current switch off."""
        tests.helper.oh_item.set_state("Unittest_Current_Switch", "ON")
        self._rule_with_current.to_Auto_WaitCurrent()
        tests.helper.oh_item.item_state_change_event("Unittest_Current", 2)
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_WaitCurrent")
        tests.helper.oh_item.assert_value("Unittest_Current_Switch", "ON")

        tests.helper.oh_item.item_state_change_event("Unittest_Current", 0.09)
        tests.helper.oh_item.assert_value("Unittest_Current_State", "Auto_WaitCurrentExtended")
        tests.helper.oh_item.assert_value("Unittest_Current_Switch", "ON")
