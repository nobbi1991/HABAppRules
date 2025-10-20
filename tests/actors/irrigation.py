"""Test irrigation rule."""

import collections
import datetime
import unittest.mock

import HABApp

import habapp_rules.actors.config.irrigation
import habapp_rules.actors.irrigation
import habapp_rules.core.exceptions
import tests.helper.oh_item
import tests.helper.test_case_base


class TestIrrigation(tests.helper.test_case_base.TestCaseBase):
    """Tests for Irrigation."""

    def setUp(self) -> None:
        """Set up test cases."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_valve", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_active", "OFF")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_hour", 12)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_minute", 30)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_duration", 5)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_repetitions", 3)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_brake", 10)

        config = habapp_rules.actors.config.irrigation.IrrigationConfig(
            items=habapp_rules.actors.config.irrigation.IrrigationItems(valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration"), parameter=None
        )

        self._irrigation_min = habapp_rules.actors.irrigation.Irrigation(config)

    def test__init__(self) -> None:
        """Test __init__."""
        self.assertIsNone(self._irrigation_min._config.items.repetitions)
        self.assertIsNone(self._irrigation_min._config.items.brake)

        # init max
        config_max = habapp_rules.actors.config.irrigation.IrrigationConfig(
            items=habapp_rules.actors.config.irrigation.IrrigationItems(
                valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", repetitions="Unittest_repetitions", brake="Unittest_brake"
            ),
            parameter=None,
        )

        irrigation_max = habapp_rules.actors.irrigation.Irrigation(config_max)
        self.assertEqual(3, irrigation_max._config.items.repetitions.value)
        self.assertEqual(10, irrigation_max._config.items.brake.value)

    def test_init_with_none(self) -> None:
        """Test __init__ with None values."""
        tests.helper.oh_item.set_state("Unittest_valve", None)
        tests.helper.oh_item.set_state("Unittest_active", None)
        tests.helper.oh_item.set_state("Unittest_hour", None)
        tests.helper.oh_item.set_state("Unittest_minute", None)
        tests.helper.oh_item.set_state("Unittest_duration", None)
        tests.helper.oh_item.set_state("Unittest_repetitions", None)
        tests.helper.oh_item.set_state("Unittest_brake", None)

        config = habapp_rules.actors.config.irrigation.IrrigationConfig(
            items=habapp_rules.actors.config.irrigation.IrrigationItems(
                valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", repetitions="Unittest_repetitions", brake="Unittest_brake"
            ),
            parameter=None,
        )

        habapp_rules.actors.irrigation.Irrigation(config)

    def test_get_target_valve_state(self) -> None:
        """Test _get_target_valve_state."""
        # irrigation is not active
        for state in (None, "OFF"):
            tests.helper.oh_item.set_state("Unittest_active", state)
            self.assertFalse(self._irrigation_min._get_target_valve_state())

        # irrigation is active
        tests.helper.oh_item.set_state("Unittest_active", "ON")
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
        config_max = habapp_rules.actors.config.irrigation.IrrigationConfig(
            items=habapp_rules.actors.config.irrigation.IrrigationItems(
                valve="Unittest_valve", active="Unittest_active", hour="Unittest_hour", minute="Unittest_minute", duration="Unittest_duration", repetitions="Unittest_repetitions", brake="Unittest_brake"
            ),
            parameter=None,
        )

        irrigation_max = habapp_rules.actors.irrigation.Irrigation(config_max)
        tests.helper.oh_item.set_state("Unittest_active", "ON")
        tests.helper.oh_item.set_state("Unittest_repetitions", 2)

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
        # called from cyclic call
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", return_value=True):
            self._irrigation_min._cb_set_valve_state()
        self.assertEqual("ON", self._irrigation_min._config.items.valve.value)

        # called by event
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", return_value=False):
            self._irrigation_min._cb_set_valve_state(HABApp.openhab.events.ItemStateChangedEvent("Unittest_active", "ON", "OFF"))
        self.assertEqual("OFF", self._irrigation_min._config.items.valve.value)

        # same state -> no oh command
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", return_value=False), unittest.mock.patch.object(self._irrigation_min._config.items, "valve") as valve_mock:
            valve_mock.is_on.return_value = False
            self._irrigation_min._cb_set_valve_state()
        valve_mock.oh_send_command.assert_not_called()

        # exception at _get_target_valve_stat
        tests.helper.oh_item.set_state("Unittest_valve", "ON")
        with unittest.mock.patch.object(self._irrigation_min, "_get_target_valve_state", side_effect=habapp_rules.core.exceptions.HabAppRulesError("Could not get target state")):
            self._irrigation_min._cb_set_valve_state()
        self.assertEqual("OFF", self._irrigation_min._config.items.valve.value)
