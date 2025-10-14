"""Tests for motion sensors."""

import collections
import pathlib
import sys
import unittest
import unittest.mock

import HABApp

import habapp_rules.core.exceptions
import habapp_rules.sensors.config.motion
import habapp_rules.sensors.motion
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base


class TestMotion(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing motion sensors rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_min_raw", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_min_filtered", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_max_raw", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_max_filtered", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion_max_lock", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Brightness_Threshold", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Motion_Unittest_Motion_min_raw_state", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "CustomState", None)

        config_min = habapp_rules.sensors.config.motion.MotionConfig(
            items=habapp_rules.sensors.config.motion.MotionItems(motion_raw="Unittest_Motion_min_raw", motion_filtered="Unittest_Motion_min_filtered", state="H_Motion_Unittest_Motion_min_raw_state")
        )

        config_max = habapp_rules.sensors.config.motion.MotionConfig(
            items=habapp_rules.sensors.config.motion.MotionItems(
                motion_raw="Unittest_Motion_max_raw",
                motion_filtered="Unittest_Motion_max_filtered",
                brightness="Unittest_Brightness",
                brightness_threshold="Unittest_Brightness_Threshold",
                sleep_state="Unittest_Sleep_state",
                lock="Unittest_Motion_max_lock",
                state="CustomState",
            ),
            parameter=habapp_rules.sensors.config.motion.MotionParameter(extended_motion_time=5),
        )

        self.motion_min = habapp_rules.sensors.motion.Motion(config_min)
        self.motion_max = habapp_rules.sensors.motion.Motion(config_max)

    def test__init__(self) -> None:
        """Test __init__."""
        expected_states = [
            {"name": "Locked"},
            {"name": "SleepLocked"},
            {"name": "PostSleepLocked", "timeout": 99, "on_timeout": "timeout_post_sleep_locked"},
            {"name": "Unlocked", "initial": "Init", "children": [{"name": "Init"}, {"name": "Wait"}, {"name": "Motion"}, {"name": "MotionExtended", "timeout": 99, "on_timeout": "timeout_motion_extended"}, {"name": "TooBright"}]},
        ]
        self.assertEqual(expected_states, self.motion_min.states)

        expected_trans = [
            {"trigger": "lock_on", "source": ["Unlocked", "SleepLocked", "PostSleepLocked"], "dest": "Locked"},
            {"trigger": "lock_off", "source": "Locked", "dest": "Unlocked", "unless": "_sleep_active"},
            {"trigger": "lock_off", "source": "Locked", "dest": "SleepLocked", "conditions": "_sleep_active"},
            {"trigger": "sleep_started", "source": ["Unlocked", "PostSleepLocked"], "dest": "SleepLocked"},
            {"trigger": "sleep_end", "source": "SleepLocked", "dest": "Unlocked", "unless": "_post_sleep_lock_configured"},
            {"trigger": "sleep_end", "source": "SleepLocked", "dest": "PostSleepLocked", "conditions": "_post_sleep_lock_configured"},
            {"trigger": "timeout_post_sleep_locked", "source": "PostSleepLocked", "dest": "Unlocked", "unless": "_raw_motion_active"},
            {"trigger": "motion_off", "source": "PostSleepLocked", "dest": "PostSleepLocked"},
            {"trigger": "motion_on", "source": "PostSleepLocked", "dest": "PostSleepLocked"},
            {"trigger": "motion_on", "source": "Unlocked_Wait", "dest": "Unlocked_Motion"},
            {"trigger": "motion_off", "source": "Unlocked_Motion", "dest": "Unlocked_MotionExtended", "conditions": "_motion_extended_configured"},
            {"trigger": "motion_off", "source": "Unlocked_Motion", "dest": "Unlocked_Wait", "unless": "_motion_extended_configured"},
            {"trigger": "timeout_motion_extended", "source": "Unlocked_MotionExtended", "dest": "Unlocked_Wait", "unless": "_brightness_over_threshold"},
            {"trigger": "timeout_motion_extended", "source": "Unlocked_MotionExtended", "dest": "Unlocked_TooBright", "conditions": "_brightness_over_threshold"},
            {"trigger": "motion_on", "source": "Unlocked_MotionExtended", "dest": "Unlocked_Motion"},
            {"trigger": "brightness_over_threshold", "source": "Unlocked_Wait", "dest": "Unlocked_TooBright"},
            {"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Wait", "unless": "_raw_motion_active"},
            {"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Motion", "conditions": "_raw_motion_active"},
        ]
        self.assertEqual(expected_trans, self.motion_min.trans)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "Motion"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        motion_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self.motion_min.states, transitions=self.motion_min.trans, initial=self.motion_min.state, show_conditions=True)

        motion_graph.get_graph().draw(picture_dir / "Motion.png", format="png", prog="dot")

    def test_initial_state(self) -> None:
        """Test _get_initial_state."""
        tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 100)
        tests.helper.oh_item.item_state_change_event("Unittest_Brightness_Threshold", 1000)

        TestCase = collections.namedtuple("TestCase", "locked, sleep_state, brightness, motion_raw, expected_state_max, expected_state_min")

        test_cases = [
            TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, motion_raw=False, expected_state_max="Unlocked_Wait", expected_state_min="Unlocked_Wait"),
            TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, motion_raw=True, expected_state_max="Unlocked_Motion", expected_state_min="Unlocked_Motion"),
            TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, motion_raw=False, expected_state_max="Unlocked_TooBright", expected_state_min="Unlocked_Wait"),
            TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, motion_raw=True, expected_state_max="Unlocked_TooBright", expected_state_min="Unlocked_Motion"),
            TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, motion_raw=False, expected_state_max="SleepLocked", expected_state_min="Unlocked_Wait"),
            TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, motion_raw=True, expected_state_max="SleepLocked", expected_state_min="Unlocked_Motion"),
            TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, motion_raw=False, expected_state_max="SleepLocked", expected_state_min="Unlocked_Wait"),
            TestCase(locked=False, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, motion_raw=True, expected_state_max="SleepLocked", expected_state_min="Unlocked_Motion"),
            TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, motion_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
            TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=500, motion_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Motion"),
            TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, motion_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
            TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.AWAKE.value, brightness=1500, motion_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Motion"),
            TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, motion_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
            TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=500, motion_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Motion"),
            TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, motion_raw=False, expected_state_max="Locked", expected_state_min="Unlocked_Wait"),
            TestCase(locked=True, sleep_state=habapp_rules.system.SleepState.SLEEPING.value, brightness=1500, motion_raw=True, expected_state_max="Locked", expected_state_min="Unlocked_Motion"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_Motion_max_lock", "ON" if test_case.locked else "OFF")
                tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_state)
                tests.helper.oh_item.set_state("Unittest_Brightness", test_case.brightness)
                tests.helper.oh_item.set_state("Unittest_Motion_max_raw", "ON" if test_case.motion_raw else "OFF")
                tests.helper.oh_item.set_state("Unittest_Motion_min_raw", "ON" if test_case.motion_raw else "OFF")

                self.assertEqual(test_case.expected_state_max, self.motion_max._get_initial_state("test"))
                self.assertEqual(test_case.expected_state_min, self.motion_min._get_initial_state("test"))

    def test_raw_motion_active(self) -> None:
        """Test _raw_motion_active."""
        tests.helper.oh_item.set_state("Unittest_Motion_min_raw", "ON")
        self.assertTrue(self.motion_min._raw_motion_active())

        tests.helper.oh_item.set_state("Unittest_Motion_min_raw", "OFF")
        self.assertFalse(self.motion_min._raw_motion_active())

    def test_get_brightness_threshold(self) -> None:
        """Test _get_brightness_threshold."""
        # value of threshold item
        self.assertEqual(float("inf"), self.motion_max._get_brightness_threshold())

        # value given as parameter
        self.motion_max._config.parameter.brightness_threshold = 800
        self.assertEqual(800, self.motion_max._get_brightness_threshold())

    def test_get_brightness_threshold_exceptions(self) -> None:
        """Test exceptions of _get_brightness_threshold."""
        self.motion_max._config.items.brightness_threshold = None
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesError):
            self.motion_max._get_brightness_threshold()

    def test_initial_unlock_state(self) -> None:
        """Test initial state of unlock state."""
        self.assertEqual(float("inf"), self.motion_max._get_brightness_threshold())
        tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 100)
        tests.helper.oh_item.item_state_change_event("Unittest_Brightness_Threshold", 1000)
        self.assertEqual(1000, self.motion_max._get_brightness_threshold())

        TestCase = collections.namedtuple("TestCase", "brightness_value, motion_raw, expected_state_min, expected_state_max")

        test_cases = [
            TestCase(100, False, expected_state_min="Unlocked_Wait", expected_state_max="Unlocked_Wait"),
            TestCase(100, True, expected_state_min="Unlocked_Motion", expected_state_max="Unlocked_Motion"),
            TestCase(2000, False, expected_state_min="Unlocked_Wait", expected_state_max="Unlocked_TooBright"),
            TestCase(2000, True, expected_state_min="Unlocked_Motion", expected_state_max="Unlocked_TooBright"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_Brightness", test_case.brightness_value)
                tests.helper.oh_item.set_state("Unittest_Motion_min_raw", "ON" if test_case.motion_raw else "OFF")
                tests.helper.oh_item.set_state("Unittest_Motion_max_raw", "ON" if test_case.motion_raw else "OFF")

                self.motion_min.to_Unlocked()
                self.motion_max.to_Unlocked()

                self.assertEqual(test_case.expected_state_min, self.motion_min.state)
                self.assertEqual(test_case.expected_state_max, self.motion_max.state)

    def test_lock(self) -> None:
        """Test if lock is activated from all states."""
        for state in self._get_state_names(self.motion_max.states):
            tests.helper.oh_item.set_state("Unittest_Motion_max_lock", "OFF")
            self.motion_max.state = state
            tests.helper.oh_item.send_command("Unittest_Motion_max_lock", "ON", "OFF")
            self.assertEqual("Locked", self.motion_max.state)

    def test_motion_extended_configured(self) -> None:
        """Test _motion_extended_configured."""
        self.motion_max._config.parameter.extended_motion_time = -1
        self.assertFalse(self.motion_max._motion_extended_configured())

        self.motion_max._config.parameter.extended_motion_time = 0
        self.assertFalse(self.motion_max._motion_extended_configured())

        self.motion_max._config.parameter.extended_motion_time = 1
        self.assertTrue(self.motion_max._motion_extended_configured())

    def test_post_sleep_lock_configured(self) -> None:
        """Test _post_sleep_lock_configured."""
        self.motion_max._config.parameter.post_sleep_lock_time = -1
        self.assertFalse(self.motion_max._post_sleep_lock_configured())

        self.motion_max._config.parameter.post_sleep_lock_time = 0
        self.assertFalse(self.motion_max._post_sleep_lock_configured())

        self.motion_max._config.parameter.post_sleep_lock_time = 1
        self.assertTrue(self.motion_max._post_sleep_lock_configured())

    def test_sleep_active(self) -> None:
        """Test _sleep_active."""
        tests.helper.oh_item.set_state("Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
        self.assertFalse(self.motion_max._sleep_active())

        tests.helper.oh_item.set_state("Unittest_Sleep_state", habapp_rules.system.SleepState.SLEEPING.value)
        self.assertTrue(self.motion_max._sleep_active())

    def test_transitions_locked(self) -> None:
        """Test leaving transitions of locked state."""
        # to Unlocked
        self.motion_max.state = "Locked"
        with unittest.mock.patch.object(self.motion_max, "_sleep_active", return_value=False):
            tests.helper.oh_item.send_command("Unittest_Motion_max_lock", "OFF", "ON")
        self.assertEqual("Unlocked_Wait", self.motion_max.state)

        # to SleepLocked
        self.motion_max.state = "Locked"
        with unittest.mock.patch.object(self.motion_max, "_sleep_active", return_value=True):
            tests.helper.oh_item.send_command("Unittest_Motion_max_lock", "OFF", "ON")
        self.assertEqual("SleepLocked", self.motion_max.state)

    def test_transitions_sleep_locked(self) -> None:
        """Test leaving transitions of sleep locked state."""
        # to Unlocked
        self.motion_max.state = "SleepLocked"
        with unittest.mock.patch.object(self.motion_max, "_post_sleep_lock_configured", return_value=False):
            self.motion_max.sleep_end()
        self.assertEqual("Unlocked_Wait", self.motion_max.state)

        # to PostSleepLocked
        self.motion_max.state = "SleepLocked"
        with unittest.mock.patch.object(self.motion_max, "_post_sleep_lock_configured", return_value=True):
            self.motion_max.sleep_end()
        self.assertEqual("PostSleepLocked", self.motion_max.state)

    def test_transitions_post_sleep_locked(self) -> None:
        """Test leaving transitions of post sleep locked state."""
        # to Unlocked | motion not active
        self.motion_max.state = "PostSleepLocked"
        with unittest.mock.patch.object(self.motion_max, "_raw_motion_active", return_value=False):
            self.motion_max.timeout_post_sleep_locked()
            self.assertEqual("Unlocked_Wait", self.motion_max.state)

        # no change after timeout and motion
        self.motion_max.state = "PostSleepLocked"
        with unittest.mock.patch.object(self.motion_max, "_raw_motion_active", return_value=True):
            self.motion_max.timeout_post_sleep_locked()
            self.assertEqual("PostSleepLocked", self.motion_max.state)

        # reset timer if motion off
        self.motion_max.state = "PostSleepLocked"
        self.transitions_timer_mock.reset_mock()
        tests.helper.oh_item.item_state_change_event("Unittest_Motion_max_raw", "OFF", "ON")
        self.assertEqual("PostSleepLocked", self.motion_max.state)
        self.assertEqual(1, self.transitions_timer_mock.call_count)

        # reset timer if motion on
        self.motion_max.state = "PostSleepLocked"
        self.transitions_timer_mock.reset_mock()
        tests.helper.oh_item.item_state_change_event("Unittest_Motion_max_raw", "ON", "OFF")
        self.assertEqual("PostSleepLocked", self.motion_max.state)
        self.assertEqual(1, self.transitions_timer_mock.call_count)

        # sleep starts during post sleep
        self.motion_max.state = "PostSleepLocked"
        tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", habapp_rules.system.SleepState.SLEEPING.value)
        self.assertEqual("SleepLocked", self.motion_max.state)

    def test_unlocked_wait(self) -> None:
        """Test leaving transitions of Unlocked_Wait state."""
        # to motion
        self.motion_max.state = "Unlocked_Wait"
        self.motion_max.motion_on()
        self.assertEqual("Unlocked_Motion", self.motion_max.state)

        # to TooBright
        self.motion_max.state = "Unlocked_Wait"
        self.motion_max.brightness_over_threshold()
        self.assertEqual("Unlocked_TooBright", self.motion_max.state)

    def test_unlocked_motion(self) -> None:
        """Test leaving transitions of Unlocked_Motion state."""
        # motion off | extended active
        self.motion_max.state = "Unlocked_Motion"
        with unittest.mock.patch.object(self.motion_max, "_motion_extended_configured", return_value=True):
            self.motion_max.motion_off()
        self.assertEqual("Unlocked_MotionExtended", self.motion_max.state)

        # motion off | extended not active
        self.motion_max.state = "Unlocked_Motion"
        with unittest.mock.patch.object(self.motion_max, "_motion_extended_configured", return_value=False):
            self.motion_max.motion_off()
        self.assertEqual("Unlocked_Wait", self.motion_max.state)

    def test_unlocked_motion_extended(self) -> None:
        """Test leaving transitions of Unlocked_MotionExtended state."""
        # timeout | brightness over threshold
        self.motion_max.state = "Unlocked_MotionExtended"
        with unittest.mock.patch.object(self.motion_max, "_brightness_over_threshold", return_value=True):
            self.motion_max.timeout_motion_extended()
            self.assertEqual("Unlocked_TooBright", self.motion_max.state)

        # timeout | brightness below threshold
        self.motion_max.state = "Unlocked_MotionExtended"
        with unittest.mock.patch.object(self.motion_max, "_brightness_over_threshold", return_value=False):
            self.motion_max.timeout_motion_extended()
            self.assertEqual("Unlocked_Wait", self.motion_max.state)

        # motion on
        self.motion_max.state = "Unlocked_MotionExtended"
        self.motion_max.motion_on()
        self.assertEqual("Unlocked_Motion", self.motion_max.state)

    def test_unlocked_too_bright(self) -> None:
        """Test leaving transitions of Unlocked_TooBright state."""
        # motion not active
        self.motion_max.state = "Unlocked_TooBright"
        with unittest.mock.patch.object(self.motion_max, "_raw_motion_active", return_value=False):
            self.motion_max.brightness_below_threshold()
        self.assertEqual("Unlocked_Wait", self.motion_max.state)

        # motion active
        self.motion_max.state = "Unlocked_TooBright"
        with unittest.mock.patch.object(self.motion_max, "_raw_motion_active", return_value=True):
            self.motion_max.brightness_below_threshold()
        self.assertEqual("Unlocked_Motion", self.motion_max.state)

    def test_check_brightness(self) -> None:
        """Test _check_brightness."""
        with (
            unittest.mock.patch.object(self.motion_max._hysteresis_switch, "get_output", return_value=True),
            unittest.mock.patch.object(self.motion_max, "brightness_over_threshold"),
            unittest.mock.patch.object(self.motion_max, "brightness_below_threshold"),
        ):
            self.motion_max._check_brightness()
            self.motion_max.brightness_over_threshold.assert_called_once()
            self.motion_max.brightness_below_threshold.assert_not_called()

        with (
            unittest.mock.patch.object(self.motion_max._hysteresis_switch, "get_output", return_value=False),
            unittest.mock.patch.object(self.motion_max, "brightness_over_threshold"),
            unittest.mock.patch.object(self.motion_max, "brightness_below_threshold"),
        ):
            self.motion_max._check_brightness()
            self.motion_max.brightness_over_threshold.assert_not_called()
            self.motion_max.brightness_below_threshold.assert_called_once()

    def test_cb_brightness_threshold_change(self) -> None:
        """Test _cb_threshold_change."""
        with unittest.mock.patch.object(self.motion_max._hysteresis_switch, "set_threshold_on"), unittest.mock.patch.object(self.motion_max, "_check_brightness"):
            tests.helper.oh_item.item_state_change_event("Unittest_Brightness_Threshold", 42)
            self.motion_max._hysteresis_switch.set_threshold_on.assert_called_once_with(42)
            self.motion_max._check_brightness.assert_called_once()

    def test_cb_motion_raw(self) -> None:
        """Test _cb_motion_raw."""
        with unittest.mock.patch.object(self.motion_max, "motion_on"), unittest.mock.patch.object(self.motion_max, "motion_off"):
            tests.helper.oh_item.item_state_change_event("Unittest_Motion_max_raw", "ON", "OFF")
            self.motion_max.motion_on.assert_called_once()
            self.motion_max.motion_off.assert_not_called()

        with unittest.mock.patch.object(self.motion_max, "motion_on"), unittest.mock.patch.object(self.motion_max, "motion_off"):
            tests.helper.oh_item.item_state_change_event("Unittest_Motion_max_raw", "OFF", "ON")
            self.motion_max.motion_on.assert_not_called()
            self.motion_max.motion_off.assert_called_once()

    def test_cb_brightness_change(self) -> None:
        """Test _cb_threshold_change."""
        with unittest.mock.patch.object(self.motion_max, "_check_brightness"):
            tests.helper.oh_item.item_state_change_event("Unittest_Brightness", 42)
            self.motion_max._check_brightness.assert_called_once()

    def test_cb_sleep(self) -> None:
        """Test _cb_sleep."""
        for state in habapp_rules.system.SleepState:
            with unittest.mock.patch.object(self.motion_max, "sleep_started"), unittest.mock.patch.object(self.motion_max, "sleep_end"):
                tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", state.value)
                if state == habapp_rules.system.SleepState.SLEEPING:
                    self.motion_max.sleep_started.assert_called_once()
                    self.motion_max.sleep_end.assert_not_called()

                elif state == habapp_rules.system.SleepState.AWAKE:
                    self.motion_max.sleep_started.assert_not_called()
                    self.motion_max.sleep_end.assert_called_once()

                else:
                    self.motion_max.sleep_started.assert_not_called()
                    self.motion_max.sleep_end.assert_not_called()
