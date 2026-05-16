"""Test irrigation rule."""

import collections
import datetime
import unittest.mock

from HABApp.openhab.events import ItemStateChangedEvent
from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.actors.config.irrigation import IrrigationConfig, IrrigationItems
from habapp_rules.actors.irrigation import Irrigation
from habapp_rules.core.exceptions import HabAppRulesError
from tests.helper.oh_item import add_mock_item, assert_item_value, set_item_state
from tests.helper.test_case_base import TestCaseBase


class TestIrrigation(TestCaseBase):
    """Tests for Irrigation."""

    def setUp(self) -> None:
        """Set up test cases."""
        TestCaseBase.setUp(self)

        add_mock_item(SwitchItem, "Unittest_valve", "OFF")
        add_mock_item(SwitchItem, "Unittest_active", "OFF")
        add_mock_item(NumberItem, "Unittest_hour", 12)
        add_mock_item(NumberItem, "Unittest_minute", 30)
        add_mock_item(NumberItem, "Unittest_duration", 5)
        add_mock_item(NumberItem, "Unittest_repetitions", 3)
        add_mock_item(NumberItem, "Unittest_brake", 10)

        config = IrrigationConfig(items=IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration"), parameter=None)

        self._irrigation_min = Irrigation(config)

    def test__init__(self) -> None:
        """Test __init__."""
        self.assertIsNone(self._irrigation_min._config.items.repetitions)
        self.assertIsNone(self._irrigation_min._config.items.brake)

        # init max
        config_max = IrrigationConfig(
            items=IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", repetitions="Unittest_repetitions", brake="Unittest_brake"),
            parameter=None,
        )

        irrigation_max = Irrigation(config_max)
        self.assertEqual(3, irrigation_max._config.items.repetitions.value)
        self.assertEqual(10, irrigation_max._config.items.brake.value)

    def test_init_with_none(self) -> None:
        """Test __init__ with None values."""
        set_item_state("Unittest_valve", None)
        set_item_state("Unittest_active", None)
        set_item_state("Unittest_hour", None)
        set_item_state("Unittest_minute", None)
        set_item_state("Unittest_duration", None)
        set_item_state("Unittest_repetitions", None)
        set_item_state("Unittest_brake", None)

        config = IrrigationConfig(
            items=IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", repetitions="Unittest_repetitions", brake="Unittest_brake"),
            parameter=None,
        )

        Irrigation(config)

    def test_get_target_valve_state(self) -> None:
        """Test _get_target_valve_state."""
        # irrigation is active
        set_item_state("Unittest_active", "ON")
        datetime_now = datetime.datetime(2023, 1, 1, 12, 00)
        with unittest.mock.patch("datetime.datetime") as datetime_mock, unittest.mock.patch.object(self._irrigation_min, "_is_in_time_range", return_value=False):
            datetime_mock.now.return_value = datetime_now
            self.assertFalse(self._irrigation_min._get_target_valve_state())
            datetime_mock.combine.assert_called_once_with(date=datetime_now, time=datetime.time(12, 30))
            self._irrigation_min._is_in_time_range.assert_called_once()

        with unittest.mock.patch("datetime.datetime") as datetime_mock, unittest.mock.patch.object(self._irrigation_min, "_is_in_time_range", return_value=True):
            datetime_mock.now.return_value = datetime_now
            self.assertTrue(self._irrigation_min._get_target_valve_state())
            datetime_mock.combine.assert_called_once_with(date=datetime_now, time=datetime.time(12, 30))
            self._irrigation_min._is_in_time_range.assert_called_once()

    def test_get_target_valve_state_with_repetitions(self) -> None:
        """Test _get_target_valve_state with repetitions."""
        config_max = IrrigationConfig(
            items=IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", repetitions="Unittest_repetitions", brake="Unittest_brake"),
            parameter=None,
        )

        irrigation_max = Irrigation(config_max)
        set_item_state("Unittest_active", "ON")
        set_item_state("Unittest_repetitions", 2)

        # value of hour item is None
        with unittest.mock.patch.object(self._irrigation_min._config.items.hour, "value", None):
            self.assertFalse(self._irrigation_min._get_target_valve_state())

        # value of minute item is None
        with unittest.mock.patch.object(self._irrigation_min._config.items.minute, "value", None):
            self.assertFalse(self._irrigation_min._get_target_valve_state())

        # value of duration item is None
        with unittest.mock.patch.object(self._irrigation_min._config.items.duration, "value", None):
            self.assertFalse(self._irrigation_min._get_target_valve_state())

        # hour, minute and duration are valid
        with unittest.mock.patch.object(irrigation_max, "_is_in_time_range", return_value=False):
            self.assertFalse(irrigation_max._get_target_valve_state())
            self.assertEqual(3, irrigation_max._is_in_time_range.call_count)
            irrigation_max._is_in_time_range.assert_has_calls([
                unittest.mock.call(datetime.time(12, 30), datetime.time(12, 35), unittest.mock.ANY),
                unittest.mock.call(datetime.time(12, 45), datetime.time(12, 50), unittest.mock.ANY),
                unittest.mock.call(datetime.time(13, 0), datetime.time(13, 5), unittest.mock.ANY),
            ])

        with unittest.mock.patch.object(irrigation_max, "_is_in_time_range", side_effect=[False, True]):
            self.assertTrue(irrigation_max._get_target_valve_state())
            self.assertEqual(2, irrigation_max._is_in_time_range.call_count)
            irrigation_max._is_in_time_range.assert_has_calls([
                unittest.mock.call(datetime.time(12, 30), datetime.time(12, 35), unittest.mock.ANY),
                unittest.mock.call(datetime.time(12, 45), datetime.time(12, 50), unittest.mock.ANY),
            ])

    def test_is_in_time_range(self) -> None:
        """Test _is_in_time_range."""
        TestCase = collections.namedtuple("TestCase", "start_time, end_time, time_to_check, expected_result")

        test_cases = [
            TestCase(datetime.time(12, 00), datetime.time(13, 00), datetime.time(12, 30), True),
            TestCase(datetime.time(12, 00), datetime.time(13, 00), datetime.time(14, 30), False),
            TestCase(datetime.time(12, 00), datetime.time(13, 00), datetime.time(13, 00), False),
            TestCase(datetime.time(12, 00), datetime.time(13, 00), datetime.time(12, 00), True),
            TestCase(datetime.time(23, 00), datetime.time(1, 00), datetime.time(23, 0), True),
            TestCase(datetime.time(23, 00), datetime.time(1, 00), datetime.time(23, 59), True),
            TestCase(datetime.time(23, 00), datetime.time(1, 00), datetime.time(0, 0), True),
            TestCase(datetime.time(23, 00), datetime.time(1, 00), datetime.time(0, 30), True),
            TestCase(datetime.time(23, 00), datetime.time(1, 00), datetime.time(1, 0), False),
        ]

        for test_case in test_cases:
            self.assertEqual(test_case.expected_result, self._irrigation_min._is_in_time_range(test_case.start_time, test_case.end_time, test_case.time_to_check))

    def test_cb_set_valve_state(self) -> None:
        """Test _cb_set_valve_state."""
        set_item_state("Unittest_active", "ON")

        # called from cyclic call
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", return_value=True):
            self._irrigation_min._cb_set_valve_state()
        self.assertEqual("ON", self._irrigation_min._config.items.valve.value)

        # called by event
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", return_value=False):
            self._irrigation_min._cb_set_valve_state(ItemStateChangedEvent("Unittest_active", "ON", "OFF"))
        self.assertEqual("OFF", self._irrigation_min._config.items.valve.value)

        # same state -> no oh command
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", return_value=False), unittest.mock.patch.object(self._irrigation_min._config.items, "valve") as valve_mock:
            valve_mock.is_on.return_value = False
            self._irrigation_min._cb_set_valve_state()
        valve_mock.oh_send_command.assert_not_called()

        # exception at _get_target_valve_stat
        set_item_state("Unittest_valve", "ON")
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", side_effect=HabAppRulesError("Could not get target state")):
            self._irrigation_min._cb_set_valve_state()
        self.assertEqual("OFF", self._irrigation_min._config.items.valve.value)

        # not active (by item)
        set_item_state("Unittest_active", "OFF")
        set_item_state("Unittest_valve", "ON")
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", return_value=True) as get_target_state_mock:
            self._irrigation_min._cb_set_valve_state()
        get_target_state_mock.assert_not_called()
        assert_item_value("Unittest_valve", "ON")
