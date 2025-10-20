"""Test heating rules."""

import collections
import datetime
import unittest.mock

import HABApp
import HABApp.rule.scheduler.job_ctrl

import habapp_rules.actors.config.heating
import habapp_rules.actors.heating
import tests.helper.oh_item
import tests.helper.test_case_base


class TestKnxHeating(tests.helper.test_case_base.TestCaseBase):
    """Test KnxHeating."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_OH", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature_KNX", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Offset", None)

        self._config = habapp_rules.actors.config.heating.KnxHeatingConfig(
            items=habapp_rules.actors.config.heating.KnxHeatingItems(virtual_temperature="Unittest_Temperature_OH", actor_feedback_temperature="Unittest_Temperature_KNX", temperature_offset="Unittest_Offset")
        )

        self._rule = habapp_rules.actors.heating.KnxHeating(self._config)

    def test_init(self) -> None:
        """Test __init__."""
        rule = habapp_rules.actors.heating.KnxHeating(self._config)
        self.assertIsNone(rule._temperature)

        tests.helper.oh_item.set_state("Unittest_Temperature_KNX", 42)
        rule = habapp_rules.actors.heating.KnxHeating(self._config)
        self.assertEqual(42, rule._temperature)

    def test_feedback_temperature_changed(self) -> None:
        """Test _cb_actor_feedback_temperature_changed."""
        tests.helper.oh_item.assert_value("Unittest_Temperature_OH", None)
        tests.helper.oh_item.item_state_change_event("Unittest_Temperature_KNX", 42)
        tests.helper.oh_item.assert_value("Unittest_Temperature_OH", 42)
        self.assertEqual(42, self._rule._temperature)

    def test_virtual_temperature_command(self) -> None:
        """Test _cb_virtual_temperature_command."""
        # _temperature and temperature_offset are None
        self.assertIsNone(self._rule._temperature)
        tests.helper.oh_item.assert_value("Unittest_Offset", None)

        tests.helper.oh_item.item_command_event("Unittest_Temperature_OH", 42)

        self.assertEqual(42, self._rule._temperature)
        tests.helper.oh_item.assert_value("Unittest_Offset", 0)

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
                tests.helper.oh_item.set_state("Unittest_Offset", test_case.offset_value)

                tests.helper.oh_item.item_command_event("Unittest_Temperature_OH", test_case.event_value)

                self.assertEqual(test_case.expected_new_offset, round(self._rule._config.items.temperature_offset.value, 1))
                self.assertEqual(test_case.event_value, self._rule._temperature)


class TestHeatingActive(tests.helper.test_case_base.TestCaseBase):
    """Test HeatingActive."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_ctr_value_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_ctr_value_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_heating_active_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_heating_active_2", None)

        self._config_1 = habapp_rules.actors.config.heating.HeatingActiveConfig(items=habapp_rules.actors.config.heating.HeatingActiveItems(control_values=["Unittest_ctr_value_1", "Unittest_ctr_value_2"], output="Unittest_heating_active_1"))
        self._config_2 = habapp_rules.actors.config.heating.HeatingActiveConfig(
            items=habapp_rules.actors.config.heating.HeatingActiveItems(control_values=["Unittest_ctr_value_1", "Unittest_ctr_value_2"], output="Unittest_heating_active_2"),
            parameter=habapp_rules.actors.config.heating.HeatingActiveParameter(extended_active_time=datetime.timedelta(seconds=10), threshold=20),
        )

        self._rule_1 = habapp_rules.actors.heating.HeatingActive(self._config_1)
        self._rule_2 = habapp_rules.actors.heating.HeatingActive(self._config_2)

    def test_init(self) -> None:
        """Test __init__."""
        self.assertTrue(isinstance(self._rule_1._extended_lock, HABApp.rule.scheduler.job_ctrl.CountdownJobControl))
        self.assertIsNone(self._rule_1._extended_lock.next_run_datetime)
        tests.helper.oh_item.assert_value("Unittest_heating_active_1", "OFF")
        tests.helper.oh_item.assert_value("Unittest_heating_active_2", "OFF")
        self.assertIn("_cb_lock_end", self._rule_1._extended_lock._job.executor._func.name)

    def test_init_when_output_is_on(self) -> None:
        """Test __init__ when output is on."""
        TestCase = collections.namedtuple("TestCase", "state, reset_called")

        test_cases = [TestCase("ON", True), TestCase("OFF", False), TestCase(None, False)]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_heating_active_1", test_case.state)
                with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.countdown") as run_countdown_mock:
                    habapp_rules.actors.heating.HeatingActive(self._config_1)
                if test_case.reset_called:
                    run_countdown_mock.return_value.reset.assert_called_once()
                else:
                    run_countdown_mock.return_value.reset.assert_not_called()

    def test_set_output(self) -> None:
        """Test _set_output."""
        tests.helper.oh_item.assert_value("Unittest_heating_active_1", "OFF")

        # ctr_value_1 changes to 0
        tests.helper.oh_item.item_state_change_event("Unittest_ctr_value_1", 0)
        tests.helper.oh_item.assert_value("Unittest_heating_active_1", "OFF")
        tests.helper.oh_item.assert_value("Unittest_heating_active_2", "OFF")

        # ctr_value_1 changes to 10
        tests.helper.oh_item.item_state_change_event("Unittest_ctr_value_1", 10)
        tests.helper.oh_item.assert_value("Unittest_heating_active_1", "ON")
        tests.helper.oh_item.assert_value("Unittest_heating_active_2", "OFF")

        # ctr_value_2 changes to 21
        tests.helper.oh_item.item_state_change_event("Unittest_ctr_value_2", 21)
        tests.helper.oh_item.assert_value("Unittest_heating_active_1", "ON")
        tests.helper.oh_item.assert_value("Unittest_heating_active_2", "ON")

        # both change to 0
        tests.helper.oh_item.item_state_change_event("Unittest_ctr_value_1", 0)
        tests.helper.oh_item.item_state_change_event("Unittest_ctr_value_2", 0)
        tests.helper.oh_item.assert_value("Unittest_heating_active_1", "ON")
        tests.helper.oh_item.assert_value("Unittest_heating_active_2", "ON")

        # lock period ends
        self._rule_1._cb_lock_end()
        self._rule_2._cb_lock_end()
        tests.helper.oh_item.assert_value("Unittest_heating_active_1", "OFF")
        tests.helper.oh_item.assert_value("Unittest_heating_active_2", "OFF")
