"""Test energy save switch rules."""

import collections
import sys
import unittest.mock

from HABApp.openhab.items import NumberItem, StringItem, SwitchItem

from habapp_rules.actors.config.energy_save_switch import EnergySaveSwitchConfig, EnergySaveSwitchItems, EnergySaveSwitchParameter
from habapp_rules.actors.energy_save_switch import EnergySaveSwitch
from habapp_rules.system import PresenceState, SleepState
from tests.helper.graph_machines import create_state_graphs
from tests.helper.oh_item import add_mock_item, assert_item_value, item_state_change_event, send_command, set_item_state
from tests.helper.test_case_base import TestCaseBaseStateMachine
from tests.helper.timer import call_timeout


class TestEnergySaveSwitch(TestCaseBaseStateMachine):
    """Tests cases for testing energy save switch."""

    def setUp(self) -> None:
        """Setup test case."""
        super().setUp()

        add_mock_item(SwitchItem, "Unittest_Min_Switch")
        add_mock_item(StringItem, "Unittest_Min_State")

        add_mock_item(SwitchItem, "Unittest_Max_Switch")
        add_mock_item(StringItem, "Unittest_Max_State")
        add_mock_item(SwitchItem, "Unittest_Max_Manual")
        add_mock_item(SwitchItem, "Unittest_External_Request")

        add_mock_item(SwitchItem, "Unittest_Current_Switch")
        add_mock_item(StringItem, "Unittest_Current_State")
        add_mock_item(SwitchItem, "Unittest_Current_Manual")
        add_mock_item(NumberItem, "Unittest_Current")

        add_mock_item(StringItem, "Unittest_Presence_state")
        add_mock_item(StringItem, "Unittest_Sleep_state")

        self._config_min = EnergySaveSwitchConfig(items=EnergySaveSwitchItems(switch="Unittest_Min_Switch", state="Unittest_Min_State"))

        self._config_max_without_current = EnergySaveSwitchConfig(
            items=EnergySaveSwitchItems(
                switch="Unittest_Max_Switch", state="Unittest_Max_State", manual="Unittest_Max_Manual", external_request="Unittest_External_Request", presence_state="Unittest_Presence_state", sleeping_state="Unittest_Sleep_state"
            ),
            parameter=EnergySaveSwitchParameter(max_on_time=3600, hand_timeout=1800),
        )

        self._config_current = EnergySaveSwitchConfig(
            items=EnergySaveSwitchItems(switch="Unittest_Current_Switch", state="Unittest_Current_State", manual="Unittest_Current_Manual", current="Unittest_Current", presence_state="Unittest_Presence_state", sleeping_state="Unittest_Sleep_state"),
            parameter=EnergySaveSwitchParameter(current_threshold=0.1, extended_wait_for_current_time=142),
        )

        self._rule_min = EnergySaveSwitch(self._config_min)
        self._rule_max_without_current = EnergySaveSwitch(self._config_max_without_current)
        self._rule_with_current = EnergySaveSwitch(self._config_current)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        create_state_graphs(self._rule_min, "EnergySaveSwitch")

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

        assert_item_value("Unittest_Max_State", "Auto_Off")
        assert_item_value("Unittest_Min_State", "Auto_Off")

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                item_state_change_event("Unittest_External_Request", test_case.external_req)
                item_state_change_event("Unittest_Sleep_state", test_case.sleeping_state.value)
                item_state_change_event("Unittest_Presence_state", test_case.presence_state.value)

                assert_item_value("Unittest_Max_State", test_case.expected_state)
                assert_item_value("Unittest_Max_Switch", "ON" if test_case.expected_state == "Auto_On" else "OFF")

                assert_item_value("Unittest_Min_State", "Auto_Off")

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

        assert_item_value("Unittest_Min_State", "Auto_On")
        assert_item_value("Unittest_Max_State", "Auto_Off")
        assert_item_value("Unittest_Current_State", "Auto_On")

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

                    item_state_change_event("Unittest_External_Request", test_case.external_req)
                    item_state_change_event("Unittest_Sleep_state", test_case.sleeping_state.value)
                    item_state_change_event("Unittest_Presence_state", test_case.presence_state.value)

                    assert_item_value("Unittest_Max_State", test_case.expected_state_max)
                    assert_item_value("Unittest_Max_Switch", "ON" if test_case.expected_state_max == "Auto_On" else "OFF")

                    assert_item_value("Unittest_Current_State", test_case.expected_state_current)
                    assert_item_value("Unittest_Current_Switch", "ON" if test_case.expected_state_current in {"Auto_On", "Auto_WaitCurrent"} else "OFF")

                    assert_item_value("Unittest_Min_State", "Auto_On")

    def test_auto_on_transitions_timeout(self) -> None:
        """Test auto on transitions with max_on_countdown."""
        # external request OFF
        item_state_change_event("Unittest_External_Request", "OFF")
        self._rule_max_without_current.to_Auto_On()
        self._rule_max_without_current._cb_max_on_countdown()
        assert_item_value("Unittest_Max_State", "Auto_Off")
        assert_item_value("Unittest_Max_Switch", "OFF")

        # external request ON
        item_state_change_event("Unittest_External_Request", "ON")
        self._rule_max_without_current.to_Auto_On()
        self._rule_max_without_current._cb_max_on_countdown()
        assert_item_value("Unittest_Max_State", "Auto_On")
        assert_item_value("Unittest_Max_Switch", "ON")
        # external to off
        item_state_change_event("Unittest_External_Request", "OFF")
        assert_item_value("Unittest_Max_State", "Auto_Off")
        assert_item_value("Unittest_Max_Switch", "OFF")

    def test_auto_wait_current_transitions(self) -> None:
        """Test Auto_WaitCurrent transitions."""
        # on conditions met
        self._rule_with_current.to_Auto_WaitCurrent()
        self._rule_with_current.on_conditions_met()
        assert_item_value("Unittest_Current_State", "Auto_On")
        assert_item_value("Unittest_Current_Switch", "ON")

        # current below threshold
        self._rule_with_current.to_Auto_WaitCurrent()
        self._rule_with_current.current_below_threshold()
        assert_item_value("Unittest_Current_State", "Auto_WaitCurrentExtended")
        assert_item_value("Unittest_Current_Switch", "ON")

        # max_on_countdown | external request off
        item_state_change_event("Unittest_External_Request", "OFF")
        self._rule_max_without_current.to_Auto_WaitCurrent()
        self._rule_max_without_current._cb_max_on_countdown()
        assert_item_value("Unittest_Max_State", "Auto_Off")
        assert_item_value("Unittest_Max_Switch", "OFF")

        # max_on_countdown | external request on
        item_state_change_event("Unittest_External_Request", "ON")
        self._rule_max_without_current.to_Auto_WaitCurrent()
        self._rule_max_without_current._cb_max_on_countdown()
        assert_item_value("Unittest_Max_State", "Auto_WaitCurrent")
        assert_item_value("Unittest_Max_Switch", "ON")
        # external to off
        item_state_change_event("Unittest_External_Request", "OFF")
        assert_item_value("Unittest_Max_State", "Auto_Off")
        assert_item_value("Unittest_Max_Switch", "OFF")

    def test_hand_transitions(self) -> None:
        """Test Hand transitions."""
        # max_on_countdown | external request off
        item_state_change_event("Unittest_External_Request", "OFF")
        self._rule_max_without_current.to_Hand()
        self._rule_max_without_current._cb_max_on_countdown()
        assert_item_value("Unittest_Max_State", "Auto_Off")
        assert_item_value("Unittest_Max_Switch", "OFF")

        # max_on_countdown | external request on
        item_state_change_event("Unittest_External_Request", "ON")
        self._rule_max_without_current.to_Hand()
        self._rule_max_without_current._cb_max_on_countdown()
        assert_item_value("Unittest_Max_State", "Hand")
        assert_item_value("Unittest_Max_Switch", "ON")
        # external to off
        item_state_change_event("Unittest_External_Request", "OFF")
        assert_item_value("Unittest_Max_State", "Auto_Off")
        assert_item_value("Unittest_Max_Switch", "OFF")

        # hand timeout
        self._rule_max_without_current.to_Hand()
        call_timeout(self.transitions_timer_mock)
        assert_item_value("Unittest_Current_State", "Auto_Off")
        assert_item_value("Unittest_Current_Switch", "OFF")

        # manual off
        self._rule_max_without_current.to_Hand()
        item_state_change_event("Unittest_Current_Manual", "ON")
        assert_item_value("Unittest_Current_State", "Manual")
        assert_item_value("Unittest_Current_Switch", "OFF")

    def test_to_hand_transitions(self) -> None:
        """Test to Hand transitions."""
        for state in ["Auto_On", "Auto_WaitCurrent", "Auto_Off"]:
            with self.subTest(state=state):
                eval(f"self._rule_with_current.to_{state}()")  # noqa: S307
                item_state_change_event("Unittest_Current_Switch", "OFF")
                item_state_change_event("Unittest_Current_Switch", "ON")
                assert_item_value("Unittest_Current_State", "Hand")

    def test_manual_transitions(self) -> None:
        """Test Manual transitions."""
        # manual off | on_off_conditions not met
        self._rule_with_current.to_Manual()
        item_state_change_event("Unittest_Current_Manual", "OFF")
        assert_item_value("Unittest_Current_State", "Auto_Off")

        # manual off | on_off_conditions met
        self._rule_with_current.to_Manual()
        item_state_change_event("Unittest_Presence_state", PresenceState.PRESENCE.value)
        item_state_change_event("Unittest_Sleep_state", SleepState.AWAKE.value)
        item_state_change_event("Unittest_Current_Manual", "OFF")
        assert_item_value("Unittest_Current_State", "Auto_On")

    def test_wait_current_extended_transitions(self) -> None:
        """Test WaitCurrentExtended transitions."""
        # on conditions met
        self._rule_with_current.to_Auto_WaitCurrentExtended()
        self._rule_with_current.on_conditions_met()
        assert_item_value("Unittest_Current_State", "Auto_On")

        # current above threshold
        self._rule_with_current.to_Auto_WaitCurrentExtended()
        send_command("Unittest_Current", 2)
        assert_item_value("Unittest_Current_State", "Auto_WaitCurrent")

        # extended timeout
        self._rule_with_current.to_Auto_WaitCurrentExtended()
        call_timeout(self.transitions_timer_mock)
        assert_item_value("Unittest_Current_State", "Auto_Off")

    def test_current_switch_off(self) -> None:
        """Test current switch off."""
        set_item_state("Unittest_Current_Switch", "ON")
        self._rule_with_current.to_Auto_WaitCurrent()
        item_state_change_event("Unittest_Current", 2)
        assert_item_value("Unittest_Current_State", "Auto_WaitCurrent")
        assert_item_value("Unittest_Current_Switch", "ON")

        item_state_change_event("Unittest_Current", 0.09)
        assert_item_value("Unittest_Current_State", "Auto_WaitCurrentExtended")
        assert_item_value("Unittest_Current_Switch", "ON")
