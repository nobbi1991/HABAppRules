"""Tests for Task rules."""

import collections
import datetime
import unittest.mock

from HABApp.openhab.items import DatetimeItem, NumberItem, SwitchItem

from habapp_rules.system.config.task import CounterTaskConfig, CounterTaskItems, CounterTaskParameter, RecurringTaskConfig, RecurringTaskItems, RecurringTaskParameter
from habapp_rules.system.task import CounterTask, RecurringTask
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_change_event,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBase


class TestRecurringTask(TestCaseBase):
    """Tests for RecurringTask Rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(SwitchItem, "Unittest_Task", None)
        add_mock_item(DatetimeItem, "Unittest_Task_last", None)

        config_max = RecurringTaskConfig(items=RecurringTaskItems(task_active="Unittest_Task", last_done="Unittest_Task_last"), parameter=RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=12)))

        self._rule = RecurringTask(config_max)

    def test_init_with_fixed_check_time(self) -> None:
        """Test init with fixed check time."""
        self._rule = RecurringTask(
            RecurringTaskConfig(
                items=RecurringTaskItems(task_active="Unittest_Task", last_done="Unittest_Task_last"),
                parameter=RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=12), fixed_check_time=datetime.time(7)),
            )
        )

        self.assertEqual(self._rule._config.parameter.fixed_check_time, datetime.time(7))

    def test_init_with_min_config(self) -> None:
        """Test init with minimal config."""
        add_mock_item(DatetimeItem, "H_Unittest_Task_last_done", None)

        with unittest.mock.patch("habapp_rules.system.config.task.create_additional_item", return_value=DatetimeItem("H_Unittest_Task_last_done")) as create_item_mock:
            config_min = RecurringTaskConfig(
                items=RecurringTaskItems(
                    task_active="Unittest_Task",
                ),
                parameter=RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=12)),
            )
            RecurringTask(config_min)

        create_item_mock.assert_called_once_with("H_Unittest_Task_last_done", DatetimeItem)

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
        assert_item_value("Unittest_Task_last", None)

        item_state_change_event("Unittest_Task", "ON")
        assert_item_value("Unittest_Task_last", None)

        item_state_change_event("Unittest_Task", "OFF")
        self.assertTrue(datetime.datetime.now() - self._rule._config.items.last_done.value < datetime.timedelta(seconds=1))

    def test_check_and_set_task_undone(self) -> None:
        """Test _check_and_set_task_undone."""
        # last done is None
        assert_item_value("Unittest_Task_last", None)
        assert_item_value("Unittest_Task", None)
        self._rule._check_and_set_task_undone()
        assert_item_value("Unittest_Task", "ON")

        # last done is value that should set task to undone
        item_state_change_event("Unittest_Task", "OFF")
        set_item_state("Unittest_Task_last", datetime.datetime.now() - datetime.timedelta(days=1))
        self._rule._check_and_set_task_undone()
        assert_item_value("Unittest_Task", "ON")

        # last done is value that should not set task to undone
        item_state_change_event("Unittest_Task", "OFF")
        set_item_state("Unittest_Task_last", datetime.datetime.now() - datetime.timedelta(hours=1))
        self._rule._check_and_set_task_undone()
        assert_item_value("Unittest_Task", "OFF")


class TestCounterTask(TestCaseBase):
    """Tests for CounterTask Rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(SwitchItem, "Unittest_Counter_Task", None)
        add_mock_item(NumberItem, "Unittest_Observed", None)
        add_mock_item(NumberItem, "Unittest_Observed_last_reset", None)

        config_max = CounterTaskConfig(
            items=CounterTaskItems(task_active="Unittest_Counter_Task", observed="Unittest_Observed", last_reset="Unittest_Observed_last_reset"),
            parameter=CounterTaskParameter(max_value=42),
        )

        self._rule = CounterTask(config_max)

    def test_init_with_min_config(self) -> None:
        """Test init with minimal config."""
        add_mock_item(NumberItem, "H_Unittest_Observed_last_reset", None)

        with unittest.mock.patch("habapp_rules.system.config.task.create_additional_item", return_value=NumberItem("H_Unittest_Observed_last_reset")) as create_item_mock:
            config_min = CounterTaskConfig(items=CounterTaskItems(task_active="Unittest_Counter_Task", observed="Unittest_Observed"), parameter=CounterTaskParameter(max_value=42))
            CounterTask(config_min)

        create_item_mock.assert_called_once_with("H_Unittest_Observed_last_reset", NumberItem)

    def test_overall_behaviour(self) -> None:
        """Test overall behaviour."""
        # first value
        item_state_change_event("Unittest_Observed", 20)
        assert_item_value("Unittest_Counter_Task", "OFF")

        # second value still smaller than threshold
        item_state_change_event("Unittest_Observed", 42)
        assert_item_value("Unittest_Counter_Task", "OFF")

        # value greater than threshold
        item_state_change_event("Unittest_Observed", 43)
        assert_item_value("Unittest_Counter_Task", "ON")

        # second value greater than threshold
        item_state_change_event("Unittest_Observed", 100)
        assert_item_value("Unittest_Counter_Task", "ON")

        # reset of task
        item_state_change_event("Unittest_Counter_Task", "OFF")
        assert_item_value("Unittest_Observed_last_reset", 100)

        # first value after reset
        item_state_change_event("Unittest_Observed", 142)
        assert_item_value("Unittest_Counter_Task", "OFF")

        # second value after reset
        item_state_change_event("Unittest_Observed", 143)
        assert_item_value("Unittest_Counter_Task", "ON")
