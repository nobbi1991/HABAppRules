"""Test Presence rule."""

import collections
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.state_observer
import tests.helper.oh_item
import tests.helper.test_case_base


class TestStateObserverSwitch(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing StateObserver for switch item."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch", None)

        self._cb_on = unittest.mock.MagicMock()
        self._cb_off = unittest.mock.MagicMock()
        self._observer_switch = habapp_rules.actors.state_observer.StateObserverSwitch("Unittest_Switch", cb_on=self._cb_on, cb_off=self._cb_off)

    def test_command_from_habapp(self) -> None:
        """Test HABApp rule triggers a command -> no manual should be detected."""
        for value in ["OFF", "OFF", "ON", "ON", "OFF"]:
            self._observer_switch.send_command(value)
            tests.helper.oh_item.item_command_event("Unittest_Switch", value)
            tests.helper.oh_item.item_state_change_event("Unittest_Switch", value)
            self._cb_on.assert_not_called()
            self._cb_off.assert_not_called()

    def test_manu_from_openhab(self) -> None:
        """Test manual detection from openHAB."""
        TestCase = collections.namedtuple("TestCase", "command, cb_on_called, cb_off_called")

        test_cases = [
            TestCase("ON", True, False),
            TestCase("ON", False, False),
            TestCase("OFF", False, True),
            TestCase("OFF", False, False),
            TestCase("ON", True, False),
        ]

        for test_case in test_cases:
            self._cb_on.reset_mock()
            self._cb_off.reset_mock()

            tests.helper.oh_item.item_state_change_event("Unittest_Switch", test_case.command)

            self.assertEqual(test_case.cb_on_called, self._cb_on.called)
            self.assertEqual(test_case.cb_off_called, self._cb_off.called)

            if test_case.cb_on_called:
                self._cb_on.assert_called_with(unittest.mock.ANY)
            if test_case.cb_off_called:
                self._cb_off.assert_called_with(unittest.mock.ANY)

    def test_manu_from_extern(self) -> None:
        """Test manual detection from extern."""
        TestCase = collections.namedtuple("TestCase", "command, cb_on_called, cb_off_called")

        test_cases = [
            TestCase("ON", True, False),
            TestCase("ON", False, False),
            TestCase("OFF", False, True),
            TestCase("OFF", False, False),
            TestCase("ON", True, False),
        ]

        for test_case in test_cases:
            self._cb_on.reset_mock()
            self._cb_off.reset_mock()

            tests.helper.oh_item.item_state_change_event("Unittest_Switch", test_case.command)

            self.assertEqual(test_case.cb_on_called, self._cb_on.called)
            self.assertEqual(test_case.cb_off_called, self._cb_off.called)
            if test_case.cb_on_called:
                self._cb_on.assert_called_with(unittest.mock.ANY)
            if test_case.cb_off_called:
                self._cb_off.assert_called_with(unittest.mock.ANY)
            tests.helper.oh_item.item_state_change_event("Unittest_Switch", test_case.command)
            self.assertEqual(test_case.command == "ON", self._observer_switch.value)

    def test_send_command_exception(self) -> None:
        """Test if correct exceptions is raised."""
        with self.assertRaises(ValueError):
            self._observer_switch.send_command(2)


class TestStateObserverDimmer(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing StateObserver for dimmer item."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_ctr", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_ctr", None)

        self._cb_on = unittest.mock.MagicMock()
        self._cb_off = unittest.mock.MagicMock()
        self._cb_changed = unittest.mock.MagicMock()
        self._observer_dimmer = habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Dimmer", cb_on=self._cb_on, cb_off=self._cb_off, cb_change=self._cb_changed, control_names=["Unittest_Dimmer_ctr"])

    def test_init(self) -> None:
        """Test init of StateObserverDimmer."""
        self.assertEqual([], self._observer_dimmer._StateObserverBase__group_items)
        self.assertEqual(1, len(self._observer_dimmer._StateObserverBase__control_items))
        self.assertEqual("Unittest_Dimmer_ctr", self._observer_dimmer._StateObserverBase__control_items[0].name)

        observer_dimmer = habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Dimmer", cb_on=self._cb_on, cb_off=self._cb_off, cb_change=self._cb_changed, group_names=["Unittest_Dimmer_ctr"])
        self.assertEqual(1, len(observer_dimmer._StateObserverBase__group_items))
        self.assertEqual("Unittest_Dimmer_ctr", observer_dimmer._StateObserverBase__group_items[0].name)
        self.assertEqual([], observer_dimmer._StateObserverBase__control_items)

    def test__check_item_types(self) -> None:
        """Test if wrong item types are detected correctly."""
        with self.assertRaises(TypeError) as context:
            habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Dimmer", cb_on=self._cb_on, cb_off=self._cb_off, control_names=["Unittest_Dimmer_ctr", "Unittest_Switch_ctr"])
        self.assertEqual("Found items with wrong item type. Expected: DimmerItem. Wrong: Unittest_Switch_ctr <SwitchItem>", str(context.exception))

    def test_command_from_habapp(self) -> None:
        """Test HABApp rule triggers a command -> no manual should be detected."""
        for value in [100, 0, 30, 100, 0, "ON", "OFF", 0, 80]:
            self._observer_dimmer.send_command(value)
            tests.helper.oh_item.item_command_event("Unittest_Dimmer", value)
            tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", value)
            self._cb_on.assert_not_called()
            self._cb_off.assert_not_called()
            self._cb_changed.assert_not_called()

    def test_manu_from_ctr(self) -> None:
        """Test manual detection from control item."""
        TestCase = collections.namedtuple("TestCase", "command, state, cb_on_called")

        test_cases = [TestCase("INCREASE", 30, True), TestCase("INCREASE", 40, False), TestCase("DECREASE", 20, False)]

        for test_case in test_cases:
            self._cb_on.reset_mock()
            self._cb_off.reset_mock()

            tests.helper.oh_item.item_command_event("Unittest_Dimmer_ctr", test_case.command)

            # cb_on called
            self.assertEqual(test_case.cb_on_called, self._cb_on.called)
            if test_case.cb_on_called:
                self._cb_on.assert_called_once_with(unittest.mock.ANY)

            # cb_off not called
            self._cb_off.assert_not_called()

            tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", test_case.state)
            self.assertEqual(test_case.state, self._observer_dimmer.value)

    def test_basic_behavior_on_knx(self) -> None:
        """Test basic behavior. Switch ON via KNX."""
        # === Switch ON via KNX button ===
        # set initial state
        self._cb_on.reset_mock()
        self._observer_dimmer._value = 0
        self._observer_dimmer._StateObserverDimmer__last_received_value = 0
        # In real system, this command is triggered about 2 sec later
        tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 100)
        self.assertEqual(100, self._observer_dimmer.value)
        self._cb_on.assert_called_once_with(unittest.mock.ANY)

        # === Switch ON via KNX value ===
        # set initial state
        self._cb_on.reset_mock()
        self._observer_dimmer._value = 0
        self._observer_dimmer._StateObserverDimmer__last_received_value = 0
        # In real system, this command is triggered about 2 sec later
        tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 42)
        self.assertEqual(42, self._observer_dimmer.value)
        self._cb_on.assert_called_once_with(unittest.mock.ANY)

        # === Switch ON via KNX from group ===
        # set initial state
        self._cb_on.reset_mock()
        self._observer_dimmer._value = 0
        self._observer_dimmer._StateObserverDimmer__last_received_value = 0
        # In real system, this command is triggered about 2 sec later
        tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 80)
        self.assertEqual(80, self._observer_dimmer.value)
        self._cb_on.assert_called_once_with(unittest.mock.ANY)

        # === Value via KNX from group ===
        # set initial state
        self._cb_on.reset_mock()
        self._observer_dimmer._value = 0
        self._observer_dimmer._StateObserverDimmer__last_received_value = 0
        # In real system, this command is triggered about 2 sec later
        tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 60)
        self.assertEqual(60, self._observer_dimmer.value)
        self._cb_on.assert_called_once_with(unittest.mock.ANY)

    def test_manu_from_openhab(self) -> None:
        """Test manual detection from control item."""
        TestCase = collections.namedtuple("TestCase", "command, state, cb_on_called, cb_off_called")
        self._observer_dimmer._StateObserverDimmer__last_received_value = 0

        test_cases = [
            TestCase(100, 100, True, False),
            TestCase(100, 100, False, False),
            TestCase(0, 0, False, True),
            TestCase("ON", 100.0, True, False),
            TestCase("OFF", 0.0, False, True),
        ]

        for test_case in test_cases:
            self._cb_on.reset_mock()
            self._cb_off.reset_mock()
            tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", test_case.command)

            self.assertEqual(test_case.cb_on_called, self._cb_on.called)
            self.assertEqual(test_case.cb_off_called, self._cb_off.called)
            if test_case.cb_on_called:
                self._cb_on.assert_called_once_with(unittest.mock.ANY)
            if test_case.cb_off_called:
                self._cb_off.assert_called_once_with(unittest.mock.ANY)
            tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", test_case.state)
            self.assertEqual(test_case.state, self._observer_dimmer.value)

    def test_check_manual(self) -> None:
        """Test method _check_manual."""
        TestCase = collections.namedtuple("TestCase", "event, current_value, on_called, off_called, change_called")

        test_cases = [
            TestCase(HABApp.openhab.events.ItemCommandEvent("any", "ON"), 0, True, False, False),
            TestCase(HABApp.openhab.events.ItemCommandEvent("any", "OFF"), 42, False, True, False),
            TestCase(HABApp.openhab.events.ItemCommandEvent("any", 0), 0, False, False, False),
            TestCase(HABApp.openhab.events.ItemCommandEvent("any", 42), 0, True, False, False),
            TestCase(HABApp.openhab.events.ItemCommandEvent("any", 0), 42, False, True, False),
            TestCase(HABApp.openhab.events.ItemCommandEvent("any", 42), 17, False, False, True),
            TestCase(HABApp.openhab.events.ItemCommandEvent("any", 42), 80, False, False, True),
        ]

        with (
            unittest.mock.patch.object(self._observer_dimmer, "_cb_on") as cb_on_mock,
            unittest.mock.patch.object(self._observer_dimmer, "_cb_off") as cb_off_mock,
            unittest.mock.patch.object(self._observer_dimmer, "_cb_change") as cb_change_mock,
        ):
            for test_case in test_cases:
                cb_on_mock.reset_mock()
                self._observer_dimmer._value = test_case.current_value
                cb_on_mock.reset_mock()
                cb_off_mock.reset_mock()
                cb_change_mock.reset_mock()

                self._observer_dimmer._check_manual(test_case.event)

                self.assertEqual(cb_on_mock.called, test_case.on_called)
                self.assertEqual(cb_off_mock.called, test_case.off_called)
                self.assertEqual(cb_change_mock.called, test_case.change_called)

                if test_case.on_called:
                    cb_on_mock.assert_called_once_with(test_case.event)
                if test_case.off_called:
                    cb_off_mock.assert_called_once_with(test_case.event)
                if test_case.change_called:
                    cb_change_mock.assert_called_once_with(test_case.event)

    def test_cb_group_item(self) -> None:
        """Test _cb_group_item."""
        self._observer_dimmer._group_last_event = 0
        with unittest.mock.patch("time.time") as time_mock, unittest.mock.patch.object(self._observer_dimmer, "_check_manual") as check_manual_mock:
            time_mock.return_value = 10
            self._observer_dimmer._cb_group_item(HABApp.openhab.events.ItemStateUpdatedEvent("item_name", "ON"))
            time_mock.return_value = 10.2
            self._observer_dimmer._cb_group_item(HABApp.openhab.events.ItemStateUpdatedEvent("item_name", "ON"))
        check_manual_mock.assert_called_once()

    def test_send_command_exception(self) -> None:
        """Test if correct exceptions is raised."""
        with self.assertRaises(ValueError):
            self._observer_dimmer.send_command(None)

        with self.assertRaises(ValueError):
            self._observer_dimmer.send_command("dimmer")


class TestStateObserverRollerShutter(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing StateObserver for switch item."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.RollershutterItem, "Unittest_RollerShutter", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.RollershutterItem, "Unittest_RollerShutter_ctr", None)

        self._cb_manual = unittest.mock.MagicMock()
        self._observer_jalousie = habapp_rules.actors.state_observer.StateObserverRollerShutter("Unittest_RollerShutter", cb_manual=self._cb_manual, control_names=["Unittest_RollerShutter_ctr"])

    def test_init(self) -> None:
        """Test init of StateObserverDimmer."""
        self.assertEqual([], self._observer_jalousie._StateObserverBase__group_items)
        self.assertEqual(1, len(self._observer_jalousie._StateObserverBase__control_items))
        self.assertEqual("Unittest_RollerShutter_ctr", self._observer_jalousie._StateObserverBase__control_items[0].name)

        observer_jalousie = habapp_rules.actors.state_observer.StateObserverRollerShutter("Unittest_RollerShutter", cb_manual=self._cb_manual, group_names=["Unittest_RollerShutter_ctr"])
        self.assertEqual(1, len(observer_jalousie._StateObserverBase__group_items))
        self.assertEqual("Unittest_RollerShutter_ctr", observer_jalousie._StateObserverBase__group_items[0].name)
        self.assertEqual([], observer_jalousie._StateObserverBase__control_items)

    def test_command_from_habapp(self) -> None:
        """Test HABApp rule triggers a command -> no manual should be detected."""
        for value in [100, 0, 30, 100.0, 0.0]:
            self._observer_jalousie.send_command(value)
            tests.helper.oh_item.item_command_event("Unittest_RollerShutter", value)
            tests.helper.oh_item.item_state_change_event("Unittest_RollerShutter", value)
            self._cb_manual.assert_not_called()

    def test_command_from_habapp_exception(self) -> None:
        """Test HABApp rule triggers a command with wrong type."""
        with self.assertRaises(TypeError):
            self._observer_jalousie.send_command("UP")
        self._cb_manual.assert_not_called()

    def test_manu_from_ctr(self) -> None:
        """Test manual detection from control item."""
        TestCase = collections.namedtuple("TestCase", "command, cb_manual_called")

        test_cases = [
            TestCase("DOWN", True),
            TestCase("DOWN", True),
            TestCase("UP", True),
            TestCase("UP", True),
            TestCase(0, False),
            TestCase(100, False),
        ]

        for test_case in test_cases:
            self._cb_manual.reset_mock()

            tests.helper.oh_item.item_command_event("Unittest_RollerShutter_ctr", test_case.command)

            self.assertEqual(test_case.cb_manual_called, self._cb_manual.called)
            if test_case.cb_manual_called:
                self._cb_manual.assert_called_once_with(unittest.mock.ANY)

    def test_basic_behavior_on_knx(self) -> None:
        """Test basic behavior. Switch ON via KNX."""
        # === Switch ON via KNX button ===
        # set initial state
        self._cb_manual.reset_mock()
        self._observer_jalousie._value = 0
        self._observer_jalousie._StateObserverDimmer__last_received_value = 0
        # In real system, this command is triggered about 2 sec later
        tests.helper.oh_item.item_state_change_event("Unittest_RollerShutter", 100)
        self.assertEqual(100, self._observer_jalousie.value)
        self._cb_manual.assert_called_once_with(unittest.mock.ANY)

        # === Switch ON via KNX value ===
        # set initial state
        self._cb_manual.reset_mock()
        self._observer_jalousie._value = 0
        self._observer_jalousie._StateObserverDimmer__last_received_value = 0
        # In real system, this command is triggered about 2 sec later
        tests.helper.oh_item.item_state_change_event("Unittest_RollerShutter", 42)
        self.assertEqual(42, self._observer_jalousie.value)
        self._cb_manual.assert_called_once_with(unittest.mock.ANY)

        # === Switch ON via KNX from group ===
        # set initial state
        self._cb_manual.reset_mock()
        self._observer_jalousie._value = 0
        self._observer_jalousie._StateObserverDimmer__last_received_value = 0
        # In real system, this command is triggered about 2 sec later
        tests.helper.oh_item.item_state_change_event("Unittest_RollerShutter", 80)
        self.assertEqual(80, self._observer_jalousie.value)
        self._cb_manual.assert_called_once_with(unittest.mock.ANY)

        # === Value via KNX from group ===
        # set initial state
        self._cb_manual.reset_mock()
        self._observer_jalousie._value = 0
        self._observer_jalousie._StateObserverDimmer__last_received_value = 0
        # In real system, this command is triggered about 2 sec later
        tests.helper.oh_item.item_state_change_event("Unittest_RollerShutter", 60)
        self.assertEqual(60, self._observer_jalousie.value)
        self._cb_manual.assert_called_once_with(unittest.mock.ANY)

    def test_check_manual(self) -> None:
        """Test _check_manual."""
        TestCase = collections.namedtuple("TestCase", "event, value, tolerance, cb_called")

        test_cases = [
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", None, None), 0, 0, False),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 0, None), None, 0, False),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 0, None), 0, 0, False),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 10, None), 10, 0, False),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 1, None), 0, 0, True),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 10, None), 0, 0, True),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 1, None), 0, 2, False),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 2, None), 0, 2, False),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 3, None), 0, 2, True),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 9, None), 10, 2, False),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 8, None), 10, 2, False),
            TestCase(HABApp.openhab.events.ItemStateChangedEvent("any", 7, None), 10, 2, True),
        ]

        with unittest.mock.patch.object(self._observer_jalousie, "_trigger_callback") as trigger_callback_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    trigger_callback_mock.reset_mock()
                    self._observer_jalousie._value = test_case.value
                    self._observer_jalousie._value_tolerance = test_case.tolerance

                    self._observer_jalousie._check_manual(test_case.event)

                    self.assertEqual(test_case.cb_called, trigger_callback_mock.called)


class TestStateObserverNumber(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing StateObserver for number item."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number", None)

        self._cb_manual = unittest.mock.MagicMock()
        self._observer_number = habapp_rules.actors.state_observer.StateObserverNumber("Unittest_Number", self._cb_manual, value_tolerance=0.1)

    def test_command_from_habapp(self) -> None:
        """Test HABApp rule triggers a command -> no manual should be detected."""
        for value in [0, 0, 42, 42, 0]:
            self._observer_number.send_command(value)
            tests.helper.oh_item.item_command_event("Unittest_Number", value)
            tests.helper.oh_item.item_state_change_event("Unittest_Number", value)
            self._cb_manual.assert_not_called()

    def test_manu_from_openhab(self) -> None:
        """Test manual detection from openHAB."""
        TestCase = collections.namedtuple("TestCase", "command, cb_manual_called")

        test_cases = [
            TestCase(0, False),
            TestCase(42, True),
            TestCase(0, True),
            TestCase(0, False),
            TestCase(1000, True),
        ]

        for test_case in test_cases:
            self._cb_manual.reset_mock()

            tests.helper.oh_item.item_state_change_event("Unittest_Number", test_case.command)

            self.assertEqual(test_case.cb_manual_called, self._cb_manual.called)
            if test_case.cb_manual_called:
                self._cb_manual.assert_called_with(unittest.mock.ANY)

    def test_manu_from_extern(self) -> None:
        """Test manual detection from extern."""
        TestCase = collections.namedtuple("TestCase", "command, cb_manual_called")

        test_cases = [
            TestCase(0, False),
            TestCase(42, True),
            TestCase(0, True),
            TestCase(0, False),
            TestCase(1000, True),
        ]

        for test_case in test_cases:
            self._cb_manual.reset_mock()

            tests.helper.oh_item.item_state_change_event("Unittest_Number", test_case.command)

            self.assertEqual(test_case.cb_manual_called, self._cb_manual.called)
            if test_case.cb_manual_called:
                self._cb_manual.assert_called_with(unittest.mock.ANY)
            tests.helper.oh_item.item_state_change_event("Unittest_Number", test_case.command)
            self.assertEqual(test_case.command, self._observer_number.value)

    def test_check_manual(self) -> None:
        """Test _check_manual."""
        TestCase = collections.namedtuple("TestCase", "last_value, new_value, manual_expected")

        test_cases = [
            # same value -> False
            TestCase(0, 0, False),
            TestCase(1, 1, False),
            TestCase(100, 100, False),
            # diff < 0.1 -> False
            TestCase(1, 0.9, False),
            TestCase(1, 1.09, False),
            TestCase(0.9, 1, False),
            TestCase(1.09, 1, False),
            TestCase(0, -0.1, False),
            TestCase(0, 0.1, False),
            TestCase(-0.1, 0, False),
            TestCase(0.1, 0, False),
            # diff > 0.1 -> True
            TestCase(0, 0.2, True),
            TestCase(0, -0.2, True),
            TestCase(0.2, 0, True),
            TestCase(-0.2, 0, True),
        ]

        with unittest.mock.patch.object(self._observer_number, "_trigger_callback") as trigger_cb_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    trigger_cb_mock.reset_mock()
                    self._observer_number._value = test_case.last_value
                    self._observer_number._check_manual(HABApp.openhab.events.ItemStateChangedEvent("some_name", test_case.new_value, None))
                    if test_case.manual_expected:
                        trigger_cb_mock.assert_called_once()
                    else:
                        trigger_cb_mock.assert_not_called()

    def test_send_command_exception(self) -> None:
        """Test if correct exceptions is raised."""
        with self.assertRaises(TypeError):
            self._observer_number.send_command("ON")


class TestStateObserverSlat(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing StateObserver for number / dimmer item used as slat item."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer", None)
        self._cb_manual = unittest.mock.MagicMock()
        self._observer_slat = habapp_rules.actors.state_observer.StateObserverSlat("Unittest_Dimmer", self._cb_manual)

    def test_check_manual(self) -> None:
        """Test _check_manual."""
        # value is 0
        with unittest.mock.patch("threading.Timer") as timer_mock, unittest.mock.patch("habapp_rules.actors.state_observer.StateObserverNumber._check_manual") as base_check_manual_mock:
            self._observer_slat._check_manual(event := HABApp.openhab.events.ItemStateChangedEvent("any", 0, 42))
        timer_mock.assert_called_once_with(3, self._observer_slat._StateObserverSlat__cb_check_manual_delayed, [event])
        base_check_manual_mock.assert_not_called()

        # value is 100
        with unittest.mock.patch("threading.Timer") as timer_mock, unittest.mock.patch("habapp_rules.actors.state_observer.StateObserverNumber._check_manual") as base_check_manual_mock:
            self._observer_slat._check_manual(event := HABApp.openhab.events.ItemStateChangedEvent("any", 100, 42))
        timer_mock.assert_called_once_with(3, self._observer_slat._StateObserverSlat__cb_check_manual_delayed, [event])
        base_check_manual_mock.assert_not_called()

        # other value | timer not running
        with unittest.mock.patch("threading.Timer") as timer_mock, unittest.mock.patch("habapp_rules.actors.state_observer.StateObserverNumber._check_manual") as base_check_manual_mock:
            self._observer_slat._check_manual(event := HABApp.openhab.events.ItemStateChangedEvent("any", 80, 42))
        timer_mock.assert_not_called()
        base_check_manual_mock.assert_called_once_with(self._observer_slat, event)

    def test__cb_check_manual_delayed(self) -> None:
        """Test __cb_check_manual_delayed."""
        event_mock = unittest.mock.MagicMock()
        with unittest.mock.patch("habapp_rules.actors.state_observer.StateObserverNumber._check_manual") as base_check_manual_mock:
            self._observer_slat._StateObserverSlat__cb_check_manual_delayed(event_mock)
        base_check_manual_mock.assert_called_once_with(self._observer_slat, event_mock)

    def test_on_rule_removed(self) -> None:
        """Test on_rule_removed."""
        with unittest.mock.patch.object(self._observer_slat, "_stop_timer_manual") as stop_timer_mock:
            self._observer_slat.on_rule_removed()
        stop_timer_mock.assert_called_once()
