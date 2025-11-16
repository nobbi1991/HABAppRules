"""Tests for Task rules."""

import collections
import datetime
import unittest.mock

import HABApp.openhab.items

import habapp_rules.system.config.task
import habapp_rules.system.task
import tests.helper.oh_item
import tests.helper.test_case_base


class TestRecurringTask(tests.helper.test_case_base.TestCaseBase):
    """Tests for RecurringTask Rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Task", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "Unittest_Task_last", None)

        config_max = habapp_rules.system.config.task.RecurringTaskConfig(
            items=habapp_rules.system.config.task.RecurringTaskItems(task_active="Unittest_Task", last_done="Unittest_Task_last"), parameter=habapp_rules.system.config.task.RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=12))
        )

        self._rule = habapp_rules.system.task.RecurringTask(config_max)

    def test_init_with_fixed_check_time(self) -> None:
        """Test init with fixed check time."""
        self._rule = habapp_rules.system.task.RecurringTask(
            habapp_rules.system.config.task.RecurringTaskConfig(
                items=habapp_rules.system.config.task.RecurringTaskItems(task_active="Unittest_Task", last_done="Unittest_Task_last"),
                parameter=habapp_rules.system.config.task.RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=12), fixed_check_time=datetime.time(7)),
            )
        )

        self.assertEqual(self._rule._config.parameter.fixed_check_time, datetime.time(7))

    def test_init_with_min_config(self) -> None:
        """Test init with minimal config."""
        config_min = habapp_rules.system.config.task.RecurringTaskConfig(
            items=habapp_rules.system.config.task.RecurringTaskItems(
                task_active="Unittest_Task",
            ),
            parameter=habapp_rules.system.config.task.RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=12)),
        )

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "H_Unittest_Task_last_done", None)

        with unittest.mock.patch("habapp_rules.core.helper.create_additional_item") as create_item_mock:
            habapp_rules.system.task.RecurringTask(config_min)

        create_item_mock.assert_called_once_with("H_Unittest_Task_last_done", "DateTime")

    def test__get_check_cycle(self) -> None:
        """Test _get_check_cycle()."""
        TestCase = collections.namedtuple("TestCase", "recurrence_time, expected_result")

        test_cases = [
            TestCase(datetime.timedelta(hours=12), datetime.timedelta(seconds=2160)),
            TestCase(datetime.timedelta(hours=20), datetime.timedelta(hours=1)),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._rule._config.parameter.recurrence_time = test_case.recurrence_time
                self.assertEqual(self._rule._get_check_cycle(), test_case.expected_result)

    def test_last_done_is_set(self) -> None:
        """Test if last done is set correctly."""
        tests.helper.oh_item.assert_value("Unittest_Task_last", None)

        tests.helper.oh_item.item_state_change_event("Unittest_Task", "ON")
        tests.helper.oh_item.assert_value("Unittest_Task_last", None)

        tests.helper.oh_item.item_state_change_event("Unittest_Task", "OFF")
        self.assertTrue(datetime.datetime.now() - self._rule._config.items.last_done.value < datetime.timedelta(seconds=1))

    def test_check_and_set_task_undone(self) -> None:
        """Test _check_and_set_task_undone."""
        # last done is None
        tests.helper.oh_item.assert_value("Unittest_Task_last", None)
        tests.helper.oh_item.assert_value("Unittest_Task", None)
        self._rule._check_and_set_task_undone()
        tests.helper.oh_item.assert_value("Unittest_Task", "ON")

        # last done is value that should set task to undone
        tests.helper.oh_item.item_state_change_event("Unittest_Task", "OFF")
        tests.helper.oh_item.set_state("Unittest_Task_last", datetime.datetime.now() - datetime.timedelta(days=1))
        self._rule._check_and_set_task_undone()
        tests.helper.oh_item.assert_value("Unittest_Task", "ON")

        # last done is value that should not set task to undone
        tests.helper.oh_item.item_state_change_event("Unittest_Task", "OFF")
        tests.helper.oh_item.set_state("Unittest_Task_last", datetime.datetime.now() - datetime.timedelta(hours=1))
        self._rule._check_and_set_task_undone()
        tests.helper.oh_item.assert_value("Unittest_Task", "OFF")


class TestCounterTask(tests.helper.test_case_base.TestCaseBase):
    """Tests for CounterTask Rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Counter_Task", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Observed", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Observed_last_reset", None)

        config_max = habapp_rules.system.config.task.CounterTaskConfig(
            items=habapp_rules.system.config.task.CounterTaskItems(task_active="Unittest_Counter_Task", observed="Unittest_Observed", last_reset="Unittest_Observed_last_reset"),
            parameter=habapp_rules.system.config.task.CounterTaskParameter(max_value=42),
        )

        self._rule = habapp_rules.system.task.CounterTask(config_max)

    def test_init_with_min_config(self) -> None:
        """Test init with minimal config."""
        config_min = habapp_rules.system.config.task.CounterTaskConfig(
            items=habapp_rules.system.config.task.CounterTaskItems(task_active="Unittest_Counter_Task", observed="Unittest_Observed"), parameter=habapp_rules.system.config.task.CounterTaskParameter(max_value=42)
        )

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "H_Unittest_Observed_last_reset", None)

        with unittest.mock.patch("habapp_rules.core.helper.create_additional_item") as create_item_mock:
            habapp_rules.system.task.CounterTask(config_min)

        create_item_mock.assert_called_once_with("H_Unittest_Observed_last_reset", "Number")

    def test_overall_behaviour(self) -> None:
        """Test overall behaviour."""
        # first value
        tests.helper.oh_item.item_state_change_event("Unittest_Observed", 20)
        tests.helper.oh_item.assert_value("Unittest_Counter_Task", "OFF")

        # second value still smaller than threshold
        tests.helper.oh_item.item_state_change_event("Unittest_Observed", 42)
        tests.helper.oh_item.assert_value("Unittest_Counter_Task", "OFF")

        # value greater than threshold
        tests.helper.oh_item.item_state_change_event("Unittest_Observed", 43)
        tests.helper.oh_item.assert_value("Unittest_Counter_Task", "ON")

        # second value greater than threshold
        tests.helper.oh_item.item_state_change_event("Unittest_Observed", 100)
        tests.helper.oh_item.assert_value("Unittest_Counter_Task", "ON")

        # reset of task
        tests.helper.oh_item.item_state_change_event("Unittest_Counter_Task", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Observed_last_reset", 100)

        # first value after reset
        tests.helper.oh_item.item_state_change_event("Unittest_Observed", 142)
        tests.helper.oh_item.assert_value("Unittest_Counter_Task", "OFF")

        # second value after reset
        tests.helper.oh_item.item_state_change_event("Unittest_Observed", 143)
        tests.helper.oh_item.assert_value("Unittest_Counter_Task", "ON")
