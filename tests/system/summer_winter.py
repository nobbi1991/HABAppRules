"""Tests for SummerWinter Rule."""

import collections
import datetime
import logging
import unittest.mock

import HABApp.openhab.definitions.helpers.persistence_data
import HABApp.openhab.items

import habapp_rules.system.config.summer_winter
import habapp_rules.system.summer_winter
import tests.helper.oh_item
import tests.helper.test_case_base


class TestSummerWinter(tests.helper.test_case_base.TestCaseBase):
    """Tests for SummerWinter Rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature", 0)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Summer", "OFF")

        config = habapp_rules.system.config.summer_winter.SummerWinterConfig(items=habapp_rules.system.config.summer_winter.SummerWinterItems(outside_temperature="Unittest_Temperature", summer="Unittest_Summer"))

        self._summer_winter = habapp_rules.system.summer_winter.SummerWinter(config)

    def test_init_with_none(self) -> None:
        """Test __init__ with None values."""
        tests.helper.oh_item.set_state("Unittest_Temperature", None)
        tests.helper.oh_item.set_state("Unittest_Summer", None)

        config = habapp_rules.system.config.summer_winter.SummerWinterConfig(items=habapp_rules.system.config.summer_winter.SummerWinterItems(outside_temperature="Unittest_Temperature", summer="Unittest_Summer"))

        habapp_rules.system.summer_winter.SummerWinter(config)

    def test__get_weighted_mean(self) -> None:
        """Test normal function of wighted_mean."""
        self._summer_winter._config.parameter.persistence_service = "persist_name"
        TestCase = collections.namedtuple("TestCase", "now, expected_day, temperatures, expected_mean")

        test_cases = [
            TestCase(now=datetime.datetime(2050, 1, 1, 17), expected_day=datetime.datetime(2049, 12, 31), temperatures=[[8], [18], [14]], expected_mean=13),
            TestCase(now=datetime.datetime(2050, 1, 1, 23), expected_day=datetime.datetime(2050, 1, 1), temperatures=[[8, 99], [18, 100, 100], [14]], expected_mean=13),
            TestCase(now=datetime.datetime(2050, 1, 1, 22, 59), expected_day=datetime.datetime(2049, 12, 31), temperatures=[[8], [18], [14]], expected_mean=13),
        ]

        with unittest.mock.patch.object(self._summer_winter._config.items, "outside_temperature", spec=HABApp.openhab.items.NumberItem) as outside_temp_mock:
            for test_case in test_cases:
                outside_temp_mock.get_persistence_data.reset_mock()

                # set current time
                self._summer_winter._SummerWinter__now = test_case.now

                # get historical temperatures as HABApp type and set the return to the mock item
                history_temperatures = []
                for temp_list in test_case.temperatures:
                    temp_history = HABApp.openhab.definitions.rest.persistence.ItemHistoryResp(name="some_name", data=[])
                    for idx, temp in enumerate(temp_list):
                        temp_history.data.append(HABApp.openhab.definitions.rest.persistence.DataPoint(time=idx * 123456, state=str(temp)))
                    history_temperatures.append(HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData.from_resp(temp_history))
                outside_temp_mock.get_persistence_data.side_effect = history_temperatures

                # call weighted mean and check if result is the expected mean temperature
                self.assertTrue(self._summer_winter._SummerWinter__get_weighted_mean(0), test_case.expected_mean)

                # check if call of get_persistence_data was correct
                self.assertEqual(outside_temp_mock.get_persistence_data.call_count, 3)
                outside_temp_mock.get_persistence_data.assert_any_call(persistence="persist_name", start_time=test_case.expected_day + datetime.timedelta(hours=7), end_time=test_case.expected_day + datetime.timedelta(hours=8))
                outside_temp_mock.get_persistence_data.assert_any_call(persistence="persist_name", start_time=test_case.expected_day + datetime.timedelta(hours=14), end_time=test_case.expected_day + datetime.timedelta(hours=15))
                outside_temp_mock.get_persistence_data.assert_any_call(persistence="persist_name", start_time=test_case.expected_day + datetime.timedelta(hours=22), end_time=test_case.expected_day + datetime.timedelta(hours=23))

                # call with days_in_past = 2
                outside_temp_mock.get_persistence_data.side_effect = history_temperatures
                self._summer_winter._SummerWinter__get_weighted_mean(2)

                # check if call of get_persistence_data was correct
                self.assertEqual(outside_temp_mock.get_persistence_data.call_count, 6)
                outside_temp_mock.get_persistence_data.assert_any_call(persistence="persist_name", start_time=test_case.expected_day + datetime.timedelta(days=-2, hours=7), end_time=test_case.expected_day + datetime.timedelta(days=-2, hours=8))
                outside_temp_mock.get_persistence_data.assert_any_call(persistence="persist_name", start_time=test_case.expected_day + datetime.timedelta(days=-2, hours=14), end_time=test_case.expected_day + datetime.timedelta(days=-2, hours=15))
                outside_temp_mock.get_persistence_data.assert_any_call(persistence="persist_name", start_time=test_case.expected_day + datetime.timedelta(days=-2, hours=22), end_time=test_case.expected_day + datetime.timedelta(days=-2, hours=23))

    def test__get_weighted_mean_exception(self) -> None:
        """Test normal function of wighted_mean."""
        with unittest.mock.patch.object(self._summer_winter._config.items, "outside_temperature", spec=HABApp.openhab.items.NumberItem) as outside_temp_mock, self.assertRaises(habapp_rules.system.summer_winter.SummerWinterError) as context:
            outside_temp_mock.get_persistence_data.return_value = HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData.from_resp(HABApp.openhab.definitions.rest.persistence.ItemHistoryResp(name="some_name", data=[]))
            self._summer_winter._SummerWinter__get_weighted_mean(0)
        self.assertIn("No data for", str(context.exception))

    def test__is_summer(self) -> None:
        """Test if __is_summer method is detecting summer/winter correctly."""
        self._summer_winter._config.parameter.days = 4
        self._summer_winter._SummerWinter__get_weighted_mean = unittest.mock.MagicMock()

        # check if __get_wighted_mean was called correctly
        self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [3, 3.4, 3.6, 4]
        self.assertFalse(self._summer_winter._SummerWinter__is_summer())
        self.assertEqual(self._summer_winter._SummerWinter__get_weighted_mean.call_count, 4)
        self._summer_winter._SummerWinter__get_weighted_mean.assert_any_call(0)
        self._summer_winter._SummerWinter__get_weighted_mean.assert_any_call(1)
        self._summer_winter._SummerWinter__get_weighted_mean.assert_any_call(2)
        self._summer_winter._SummerWinter__get_weighted_mean.assert_any_call(3)

        # check if summer is returned if greater than threshold
        self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [16, 16, 16, 17.1]
        self.assertTrue(self._summer_winter._SummerWinter__is_summer())

        # check if winter is returned if smaller / equal than threshold
        self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [16, 16, 16, 14]
        self.assertFalse(self._summer_winter._SummerWinter__is_summer())

        # check if exceptions are handled correctly (single Exception)
        self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [16, habapp_rules.system.summer_winter.SummerWinterError("not found"), 16.1, 18.0]
        self.assertTrue(self._summer_winter._SummerWinter__is_summer())

        # check if exceptions are handled correctly (single valid value)
        exc = habapp_rules.system.summer_winter.SummerWinterError("not found")
        self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [exc, exc, 16.1, exc]
        self.assertTrue(self._summer_winter._SummerWinter__is_summer())

        # check if exceptions are handled correctly (no value)
        exc = habapp_rules.system.summer_winter.SummerWinterError("not found")
        self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [exc, exc, exc, exc]
        with self.assertRaises(habapp_rules.system.summer_winter.SummerWinterError):
            self._summer_winter._SummerWinter__is_summer()

    def test__is_summer_with_hysteresis(self) -> None:
        """Test summer / winter with hysteresis."""
        TestCase = collections.namedtuple("TestCase", "temperature_values, summer_value, expected_summer")

        test_cases = [
            TestCase([15.74] * 5, False, False),
            TestCase([15.75] * 5, False, False),
            TestCase([15.76] * 5, False, False),
            TestCase([16.24] * 5, False, False),
            TestCase([16.25] * 5, False, True),
            TestCase([16.26] * 5, False, True),
            TestCase([15.74] * 5, True, False),
            TestCase([15.75] * 5, True, True),
            TestCase([15.76] * 5, True, True),
            TestCase([16.24] * 5, True, True),
            TestCase([16.25] * 5, True, True),
            TestCase([16.26] * 5, True, True),
        ]

        self._summer_winter._SummerWinter__get_weighted_mean = unittest.mock.MagicMock()

        for test_case in test_cases:
            self._summer_winter._SummerWinter__get_weighted_mean.side_effect = test_case.temperature_values
            self._summer_winter._hysteresis_switch._on_off_state = test_case.summer_value
            self.assertEqual(test_case.expected_summer, self._summer_winter._SummerWinter__is_summer())

    def test_cb_update_summer(self) -> None:
        """Test correct functionality of summer check callback."""
        with (
            unittest.mock.patch.object(self._summer_winter, "_SummerWinter__is_summer") as is_summer_mock,
            unittest.mock.patch.object(self._summer_winter._config.items, "last_check", spec=HABApp.openhab.items.datetime_item.DatetimeItem) as last_check_mock,
        ):
            # switch from winter to summer
            is_summer_mock.return_value = True
            self._summer_winter._cb_update_summer()
            tests.helper.oh_item.assert_value("Unittest_Summer", "ON")
            self.assertEqual(1, last_check_mock.oh_send_command.call_count)

            # already summer
            is_summer_mock.return_value = True
            with unittest.mock.patch.object(self._summer_winter._config.items, "summer") as summer_item:
                summer_item.value = "ON"
                self._summer_winter._cb_update_summer()
                summer_item.oh_send_command.assert_called_once()
                self.assertEqual(2, last_check_mock.oh_send_command.call_count)

            # switch back to winter
            is_summer_mock.return_value = False
            self._summer_winter._cb_update_summer()
            tests.helper.oh_item.assert_value("Unittest_Summer", "OFF")
            self.assertEqual(3, last_check_mock.oh_send_command.call_count)

            # already winter
            is_summer_mock.return_value = False
            with unittest.mock.patch.object(self._summer_winter._config.items, "summer") as summer_item:
                summer_item.value = "OFF"
                self._summer_winter._cb_update_summer()
                summer_item.oh_send_command.assert_called_once()
                self.assertEqual(4, last_check_mock.oh_send_command.call_count)

            # already winter | no last_check item -> send_command should not be triggered
            is_summer_mock.return_value = False
            with unittest.mock.patch.object(self._summer_winter._config.items, "summer") as summer_item:
                self._summer_winter._config.items.last_check = None
                summer_item.value = "OFF"
                self._summer_winter._cb_update_summer()
                summer_item.oh_send_command.assert_called_once()
                self.assertEqual(4, last_check_mock.oh_send_command.call_count)

        # exception from __is_summer
        with (
            unittest.mock.patch.object(self._summer_winter, "_SummerWinter__is_summer", side_effect=habapp_rules.system.summer_winter.SummerWinterError("No update")),
            unittest.mock.patch.object(self._summer_winter, "_instance_logger", spec=logging.Logger) as logger_mock,
        ):
            self._summer_winter._cb_update_summer()
            logger_mock.exception.assert_called_once()
