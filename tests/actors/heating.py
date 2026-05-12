"""Test heating rules."""

import collections
import datetime
import unittest.mock

import HABApp.rule.scheduler.job_ctrl
from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.actors.config.heating import HeatingActiveConfig, HeatingActiveItems, HeatingActiveParameter, KnxHeatingConfig, KnxHeatingItems
from habapp_rules.actors.heating import HeatingActive, KnxHeating
from tests.helper.oh_item import add_mock_item, assert_item_value, item_command_event, item_state_change_event, set_item_state
from tests.helper.test_case_base import TestCaseBase


class TestKnxHeating(TestCaseBase):
    """Test KnxHeating."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)
        add_mock_item(NumberItem, "Unittest_Temperature_OH", None)
        add_mock_item(NumberItem, "Unittest_Temperature_KNX", None)
        add_mock_item(NumberItem, "Unittest_Offset", None)

        self._config = KnxHeatingConfig(items=KnxHeatingItems(virtual_temperature="Unittest_Temperature_OH", actor_feedback_temperature="Unittest_Temperature_KNX", temperature_offset="Unittest_Offset"))

        self._rule = KnxHeating(self._config)

    def test_init(self) -> None:
        """Test __init__."""
        rule = KnxHeating(self._config)
        self.assertIsNone(rule._temperature)

        set_item_state("Unittest_Temperature_KNX", 42)
        rule = KnxHeating(self._config)
        self.assertEqual(42, rule._temperature)

    def test_feedback_temperature_changed(self) -> None:
        """Test _cb_actor_feedback_temperature_changed."""
        assert_item_value("Unittest_Temperature_OH", None)
        item_state_change_event("Unittest_Temperature_KNX", 42)
        assert_item_value("Unittest_Temperature_OH", 42)
        self.assertEqual(42, self._rule._temperature)

    def test_virtual_temperature_command(self) -> None:
        """Test _cb_virtual_temperature_command."""
        # _temperature and temperature_offset are None
        self.assertIsNone(self._rule._temperature)
        assert_item_value("Unittest_Offset", None)

        item_command_event("Unittest_Temperature_OH", 42)

        self.assertEqual(42, self._rule._temperature)
        assert_item_value("Unittest_Offset", 0)

        TestCase = collections.namedtuple("TestCase", "event_value, rule_temperature, offset_value, expected_new_offset")

        test_cases = [
            TestCase(20, 19, 0, 1),
            TestCase(21.5, 19, 0, 2.5),
            TestCase(19, 20, 0, -1),
            TestCase(15.5, 20, 0, -4.5),
            TestCase(20, 19, 1, 2),
            TestCase(21.5, 19, 1.5, 4),
            TestCase(22.4, 19, 1, 4.4),
            TestCase(20, 19, -1, 0),
            TestCase(21.5, 19, -1.5, 1),
            TestCase(22.4, 19, -1, 2.4),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._rule._temperature = test_case.rule_temperature
                set_item_state("Unittest_Offset", test_case.offset_value)

                item_command_event("Unittest_Temperature_OH", test_case.event_value)

                self.assertEqual(test_case.expected_new_offset, round(self._rule._config.items.temperature_offset.value, 1))
                self.assertEqual(test_case.event_value, self._rule._temperature)


class TestHeatingActive(TestCaseBase):
    """Test HeatingActive."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)
        add_mock_item(NumberItem, "Unittest_ctr_value_1", None)
        add_mock_item(NumberItem, "Unittest_ctr_value_2", None)
        add_mock_item(SwitchItem, "Unittest_heating_active_1", None)
        add_mock_item(SwitchItem, "Unittest_heating_active_2", None)

        self._config_1 = HeatingActiveConfig(items=HeatingActiveItems(control_values=["Unittest_ctr_value_1", "Unittest_ctr_value_2"], output="Unittest_heating_active_1"))
        self._config_2 = HeatingActiveConfig(
            items=HeatingActiveItems(control_values=["Unittest_ctr_value_1", "Unittest_ctr_value_2"], output="Unittest_heating_active_2"),
            parameter=HeatingActiveParameter(extended_active_time=datetime.timedelta(seconds=10), threshold=20),
        )

        self._rule_1 = HeatingActive(self._config_1)
        self._rule_2 = HeatingActive(self._config_2)

    def test_init(self) -> None:
        """Test __init__."""
        self.assertTrue(isinstance(self._rule_1._extended_lock, HABApp.rule.scheduler.job_ctrl.CountdownJobControl))
        self.assertIsNone(self._rule_1._extended_lock.next_run_datetime)
        assert_item_value("Unittest_heating_active_1", "OFF")
        assert_item_value("Unittest_heating_active_2", "OFF")
        self.assertIn("_cb_lock_end", self._rule_1._extended_lock._job.executor._func.name)

    def test_init_when_output_is_on(self) -> None:
        """Test __init__ when output is on."""
        TestCase = collections.namedtuple("TestCase", "state, reset_called")

        test_cases = [TestCase("ON", True), TestCase("OFF", False), TestCase(None, False)]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("Unittest_heating_active_1", test_case.state)
                with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.countdown") as run_countdown_mock:
                    HeatingActive(self._config_1)
                if test_case.reset_called:
                    run_countdown_mock.return_value.reset.assert_called_once()
                else:
                    run_countdown_mock.return_value.reset.assert_not_called()

    def test_set_output(self) -> None:
        """Test _set_output."""
        assert_item_value("Unittest_heating_active_1", "OFF")

        # ctr_value_1 changes to 0
        item_state_change_event("Unittest_ctr_value_1", 0)
        assert_item_value("Unittest_heating_active_1", "OFF")
        assert_item_value("Unittest_heating_active_2", "OFF")

        # ctr_value_1 changes to 10
        item_state_change_event("Unittest_ctr_value_1", 10)
        assert_item_value("Unittest_heating_active_1", "ON")
        assert_item_value("Unittest_heating_active_2", "OFF")

        # ctr_value_2 changes to 21
        item_state_change_event("Unittest_ctr_value_2", 21)
        assert_item_value("Unittest_heating_active_1", "ON")
        assert_item_value("Unittest_heating_active_2", "ON")

        # both change to 0
        item_state_change_event("Unittest_ctr_value_1", 0)
        item_state_change_event("Unittest_ctr_value_2", 0)
        assert_item_value("Unittest_heating_active_1", "ON")
        assert_item_value("Unittest_heating_active_2", "ON")

        # lock period ends
        self._rule_1._cb_lock_end()
        self._rule_2._cb_lock_end()
        assert_item_value("Unittest_heating_active_1", "OFF")
        assert_item_value("Unittest_heating_active_2", "OFF")
