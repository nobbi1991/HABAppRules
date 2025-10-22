"""Test bathroom light rule."""

import collections
import pathlib
import sys
import time
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.config.light_bathroom
import habapp_rules.actors.light_bathroom
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.system import PresenceState, SleepState


class TestEnergySaveSwitch(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing energy save switch."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_Main")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_Main_Ctr")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Light_Main_HCL")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Light_Main_HCL_Lock")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Light_Main_Color")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_Mirror")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_State")

        self._config = habapp_rules.actors.config.light_bathroom.BathroomLightConfig(
            items=habapp_rules.actors.config.light_bathroom.BathroomLightItems(
                light_main="Unittest_Light_Main",
                light_main_ctr="Unittest_Light_Main_Ctr",
                light_main_hcl="Unittest_Light_Main_HCL",
                light_main_color="Unittest_Light_Main_Color",
                light_mirror="Unittest_Light_Mirror",
                sleeping_state="Unittest_Sleep_state",
                presence_state="Unittest_Presence_state",
                manual="Unittest_Manual",
                state="Unittest_State",
            )
        )

        self._rule = habapp_rules.actors.light_bathroom.BathroomLight(config=self._config)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "BathroomLight"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self._rule.states, transitions=self._rule.trans, initial=self._rule.state, show_conditions=False)

        graph.get_graph().draw(picture_dir / "BathroomLight.png", format="png", prog="dot")

        for state_name in [state for state in self._get_state_names(self._rule.states) if "init" not in state.lower()]:
            graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self._rule.states, transitions=self._rule.trans, initial=state_name, show_conditions=True)
            graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"BathroomLight_{state_name}.png", format="png", prog="dot")

    def test_initial_state(self) -> None:
        """Test initial state."""
        TestCase = collections.namedtuple("TestCase", "manual, sleeping, main_light, mirror_light, expected_state")

        test_cases = [
            # manual OFF | sleeping OFF
            TestCase(manual="OFF", sleeping=False, main_light=0, mirror_light=0, expected_state="Auto_Off"),
            TestCase(manual="OFF", sleeping=False, main_light=0, mirror_light=50, expected_state="Auto_Off"),
            TestCase(manual="OFF", sleeping=False, main_light=100, mirror_light=0, expected_state="Auto_On_MainDay"),
            TestCase(manual="OFF", sleeping=False, main_light=80, mirror_light=100, expected_state="Auto_On_MainAndMirror"),
            # manual OFF | sleeping ON
            TestCase(manual="OFF", sleeping=True, main_light=0, mirror_light=0, expected_state="Auto_Off"),
            TestCase(manual="OFF", sleeping=True, main_light=0, mirror_light=50, expected_state="Auto_Off"),
            TestCase(manual="OFF", sleeping=True, main_light=100, mirror_light=0, expected_state="Auto_On_MainNight"),
            TestCase(manual="OFF", sleeping=True, main_light=80, mirror_light=100, expected_state="Auto_On_MainAndMirror"),
            # manual ON | sleeping OFF
            TestCase(manual="ON", sleeping=False, main_light=0, mirror_light=0, expected_state="Manual"),
            TestCase(manual="ON", sleeping=False, main_light=0, mirror_light=50, expected_state="Manual"),
            TestCase(manual="ON", sleeping=False, main_light=100, mirror_light=0, expected_state="Manual"),
            TestCase(manual="ON", sleeping=False, main_light=80, mirror_light=100, expected_state="Manual"),
            # manual ON | sleeping ON
            TestCase(manual="ON", sleeping=True, main_light=0, mirror_light=0, expected_state="Manual"),
            TestCase(manual="ON", sleeping=True, main_light=0, mirror_light=50, expected_state="Manual"),
            TestCase(manual="ON", sleeping=True, main_light=100, mirror_light=0, expected_state="Manual"),
            TestCase(manual="ON", sleeping=True, main_light=80, mirror_light=100, expected_state="Manual"),
        ]

        with unittest.mock.patch("habapp_rules.actors.light_bathroom.BathroomLight._is_day") as is_day_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual)
                    tests.helper.oh_item.set_state("Unittest_Light_Main", test_case.main_light)
                    tests.helper.oh_item.set_state("Unittest_Light_Mirror", test_case.mirror_light)
                    is_day_mock.return_value = not test_case.sleeping
                    rule = habapp_rules.actors.light_bathroom.BathroomLight(config=self._config)
                    self.assertEqual(test_case.expected_state, rule.state)
                    self.unload_rule(rule)

    def test_is_day(self) -> None:
        """Test _is_day."""
        TestCase = collections.namedtuple("TestCase", "sleeping_state, sleep_end_time , expected_result")

        test_cases = [
            TestCase(sleeping_state=SleepState.AWAKE.value, sleep_end_time=0, expected_result=True),
            TestCase(sleeping_state=SleepState.AWAKE.value, sleep_end_time=time.time() - 100, expected_result=False),
            TestCase(sleeping_state=SleepState.AWAKE.value, sleep_end_time=time.time() - 10000, expected_result=True),
            TestCase(sleeping_state=SleepState.SLEEPING.value, sleep_end_time=0, expected_result=False),
            TestCase(sleeping_state=SleepState.SLEEPING.value, sleep_end_time=time.time() - 100, expected_result=False),
            TestCase(sleeping_state=SleepState.SLEEPING.value, sleep_end_time=time.time() - 10000, expected_result=False),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleeping_state)
                self._rule._sleep_end_time = test_case.sleep_end_time
                self.assertEqual(test_case.expected_result, self._rule._is_day())

    def test_is_extended_sleep(self) -> None:
        """Test _is_extended_sleep."""
        TestCase = collections.namedtuple("TestCase", "sleep_end_time, time_now, expected_result")

        self._config.parameter.extended_sleep_time = 10

        test_cases = [
            TestCase(sleep_end_time=100, time_now=200, expected_result=False),
            TestCase(sleep_end_time=100, time_now=100, expected_result=True),
            TestCase(sleep_end_time=100, time_now=109, expected_result=True),
            TestCase(sleep_end_time=100, time_now=110, expected_result=True),
            TestCase(sleep_end_time=100, time_now=111, expected_result=False),
        ]

        with unittest.mock.patch("time.time", return_value=42) as time_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    self._rule._sleep_end_time = test_case.sleep_end_time
                    time_mock.return_value = test_case.time_now
                    self.assertEqual(test_case.expected_result, self._rule._is_extended_sleep())

    def test_mirror_is_on(self) -> None:
        """Test _mirror_is_on."""
        TestCase = collections.namedtuple("TestCase", "mirror_value, expected_result")

        test_cases = [
            TestCase(None, False),
            TestCase(0, False),
            TestCase(1, True),
            TestCase(42, True),
            TestCase(100, True),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_Light_Mirror", test_case.mirror_value)
                self.assertEqual(test_case.expected_result, self._rule._mirror_is_on())

    def test_set_outputs(self) -> None:
        """Test _set_outputs."""
        TestCase = collections.namedtuple("TestCase", "on_via_increase, state, main_initial, main_call, mirror, hcl, color")

        test_cases = [
            # switch_on_via_increase active
            TestCase(on_via_increase=False, state="Manual", main_initial=100, main_call=None, mirror=None, hcl=None, color=None),
            TestCase(on_via_increase=False, state="Auto_Off", main_initial=100, main_call=0, mirror="OFF", hcl=None, color=None),
            TestCase(on_via_increase=False, state="Auto_Off", main_initial=0, main_call=None, mirror="OFF", hcl=None, color=None),
            TestCase(on_via_increase=False, state="Auto_On_MainDay", main_initial=100, main_call=None, mirror=None, hcl="ON", color=None),
            TestCase(on_via_increase=False, state="Auto_On_MainNight", main_initial=100, main_call=40, mirror=None, hcl=None, color=2600),
            TestCase(on_via_increase=False, state="Auto_On_MainAndMirror", main_initial=100, main_call=100, mirror=None, hcl=None, color=4000),
            TestCase(on_via_increase=False, state="Auto_On_MainAndMirror", main_initial=60, main_call=80, mirror=None, hcl=None, color=4000),
            TestCase(on_via_increase=False, state="Auto_On_MainAndMirror", main_initial=90, main_call=90, mirror=None, hcl=None, color=4000),
            # switch_on_via_increase not active
            TestCase(on_via_increase=True, state="Manual", main_initial=100, main_call=None, mirror=None, hcl=None, color=None),
            TestCase(on_via_increase=True, state="Auto_Off", main_initial=100, main_call=0, mirror="OFF", hcl=None, color=None),
            TestCase(on_via_increase=True, state="Auto_Off", main_initial=0, main_call=None, mirror="OFF", hcl=None, color=None),
            TestCase(on_via_increase=True, state="Auto_On_MainDay", main_initial=100, main_call=None, mirror=None, hcl="ON", color=None),
            TestCase(on_via_increase=True, state="Auto_On_MainNight", main_initial=0, main_call=None, mirror=None, hcl=None, color=2600),
            TestCase(on_via_increase=True, state="Auto_On_MainAndMirror", main_initial=100, main_call=100, mirror=None, hcl=None, color=4000),
            TestCase(on_via_increase=True, state="Auto_On_MainAndMirror", main_initial=60, main_call=80, mirror=None, hcl=None, color=4000),
            TestCase(on_via_increase=True, state="Auto_On_MainAndMirror", main_initial=90, main_call=90, mirror=None, hcl=None, color=4000),
        ]

        with unittest.mock.patch("habapp_rules.core.helper.send_if_different") as send_if_different_mock, unittest.mock.patch.object(self._rule, "_light_main_observer") as main_observer_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    send_if_different_mock.reset_mock()
                    main_observer_mock.reset_mock()
                    main_observer_mock.value = test_case.main_initial
                    self._rule.state = test_case.state
                    self._rule._switch_on_via_increase = test_case.on_via_increase
                    self._rule._set_outputs()

                    self.assertEqual(send_if_different_mock.call_count, len([call for call in [test_case.mirror, test_case.hcl, test_case.color] if call is not None]))

                    if test_case.mirror is not None:
                        send_if_different_mock.assert_any_call(self._config.items.light_mirror, test_case.mirror)
                    if test_case.hcl is not None:
                        send_if_different_mock.assert_any_call(self._config.items.light_main_hcl, test_case.hcl)
                    if test_case.color is not None:
                        send_if_different_mock.assert_any_call(self._config.items.light_main_color, test_case.color)

                    if test_case.main_call is not None:
                        main_observer_mock.send_command.assert_called_once_with(test_case.main_call)
                    else:
                        main_observer_mock.send_command.assert_not_called()

                    self.assertFalse(self._rule._switch_on_via_increase)

    def test_set_outputs_sleep_extended(self) -> None:
        """Test _set_outputs for sleep and extended sleep."""
        self._config.parameter.brightness_night = 18
        self._config.parameter.brightness_night_extended = 42
        self._rule.state = "Auto_On_MainNight"

        # normal sleep
        with unittest.mock.patch.object(self._rule, "_is_extended_sleep", return_value=False):
            self._rule._set_outputs()
        tests.helper.oh_item.assert_value("Unittest_Light_Main", 18)

        # extended sleep
        with unittest.mock.patch.object(self._rule, "_is_extended_sleep", return_value=True):
            self._rule._set_outputs()
        tests.helper.oh_item.assert_value("Unittest_Light_Main", 42)

    def test_manual_transitions(self) -> None:
        """Test transitions of state Manual."""
        # set Auto as initial state
        self._rule.to_Auto()

        tests.helper.oh_item.item_state_change_event("Unittest_Manual", "ON")
        self.assertEqual("Manual", self._rule.state)

        tests.helper.oh_item.item_state_change_event("Unittest_Manual", "OFF")
        self.assertEqual("Auto_Off", self._rule.state)

    def test_auto_off_transitions(self) -> None:
        """Test transitions of state Auto_Off."""
        # set Auto as initial state
        self._rule.to_Auto()
        tests.helper.oh_item.assert_value("Unittest_State", "Auto_Off")

        with unittest.mock.patch.object(self._rule, "_is_day", return_value=True) as is_day_mock:
            # main on | day
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Main", 100)
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_On_MainDay")

            # main on | night
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Main", 0)
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_Off")
            is_day_mock.return_value = False
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Main", 100)
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_On_MainNight")

            # main on | night with INCREASE
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Main", 0)
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_Off")
            is_day_mock.return_value = False
            tests.helper.oh_item.item_command_event("Unittest_Light_Main_Ctr", "INCREASE")
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_On_MainNight")
            tests.helper.oh_item.assert_value("Unittest_Light_Main", 0)  # in reality, this will not be 0

            # main on + mirror on | day
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Main", 0)
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Mirror", 100)
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_Off")
            is_day_mock.return_value = True
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Main", 100)
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_On_MainAndMirror")

            # main on + mirror on | night
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Main", 0)
            tests.helper.oh_item.assert_value("Unittest_Light_Mirror", 0)
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Mirror", 100)
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_Off")
            is_day_mock.return_value = True
            tests.helper.oh_item.item_state_change_event("Unittest_Light_Main", 100)
            tests.helper.oh_item.assert_value("Unittest_State", "Auto_On_MainAndMirror")

    def test_sleeping_started(self) -> None:
        """Test sleeping started."""
        self.assertEqual(0, self._rule._sleep_end_time)

        TestCase = collections.namedtuple("TestCase", "sleeping_state, expected_state, expected_sleep_end_time")
        test_cases = [
            TestCase(sleeping_state=SleepState.AWAKE.value, expected_state="Auto_On_MainDay", expected_sleep_end_time=42),
            TestCase(sleeping_state=SleepState.PRE_SLEEPING.value, expected_state="Auto_Off", expected_sleep_end_time=0),
            TestCase(sleeping_state=SleepState.SLEEPING.value, expected_state="Auto_On_MainDay", expected_sleep_end_time=0),
            TestCase(sleeping_state=SleepState.POST_SLEEPING.value, expected_state="Auto_On_MainDay", expected_sleep_end_time=0),
        ]

        with unittest.mock.patch("time.time", return_value=42):
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    self._rule._sleep_end_time = 0
                    self._rule.to_Auto_On_MainDay()
                    tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", test_case.sleeping_state)
                    self.assertEqual(test_case.expected_state, self._rule.state)
                    self.assertEqual(self._rule._sleep_end_time, test_case.expected_sleep_end_time)

    def test_leaving_started(self) -> None:
        """Test leaving started."""
        self.assertEqual(0, self._rule._sleep_end_time)

        TestCase = collections.namedtuple("TestCase", "presence_state, expected_state")
        test_cases = [
            TestCase(presence_state=PresenceState.PRESENCE.value, expected_state="Auto_On_MainDay"),
            TestCase(presence_state=PresenceState.LEAVING.value, expected_state="Auto_Off"),
            TestCase(presence_state=PresenceState.ABSENCE.value, expected_state="Auto_On_MainDay"),
            TestCase(presence_state=PresenceState.LONG_ABSENCE.value, expected_state="Auto_On_MainDay"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._rule._sleep_end_time = 0
                self._rule.to_Auto_On_MainDay()
                tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", test_case.presence_state)
                self.assertEqual(test_case.expected_state, self._rule.state)
