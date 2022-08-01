"""Tests for SummerWinter Rule."""
import collections
import datetime
import logging
import unittest
import unittest.mock

import HABApp.openhab.definitions.helpers.persistence_data
import HABApp.openhab.items

import habapp_rules.system.summer_winter
import tests.helper.oh_item
import tests.helper.rule_runner


# pylint: disable=protected-access
class TestSummerWinter(unittest.TestCase):
	"""Tests for SummerWinter Rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.send_command_mock_patcher.stop)
		self.send_command_mock = self.send_command_mock_patcher.start()

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Temperature", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Summer", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "Unittest_last_check")

		self._summer_winter = habapp_rules.system.summer_winter.SummerWinter("Unittest_Temperature", "Unittest_Summer")

	def test__get_weighted_mean(self):
		"""Test normal function of wighted_mean"""
		self._summer_winter._persistence_service = "persist_name"
		TestCase = collections.namedtuple("TestCase", "now, expected_day, temperatures, expected_mean")

		test_cases = [
			TestCase(now=datetime.datetime(2050, 1, 1, 17), expected_day=datetime.datetime(2049, 12, 31), temperatures=[[8], [18], [14]], expected_mean=13),
			TestCase(now=datetime.datetime(2050, 1, 1, 23), expected_day=datetime.datetime(2050, 1, 1), temperatures=[[8, 99], [18, 100, 100], [14]], expected_mean=13),
			TestCase(now=datetime.datetime(2050, 1, 1, 22, 59), expected_day=datetime.datetime(2049, 12, 31), temperatures=[[8], [18], [14]], expected_mean=13),
		]

		with unittest.mock.patch.object(self._summer_winter, "_outside_temp_item", spec=HABApp.openhab.items.NumberItem) as outside_temp_mock:
			for test_case in test_cases:
				outside_temp_mock.get_persistence_data.reset_mock()

				# set current time
				self._summer_winter._SummerWinter__now = test_case.now

				# get historical temperatures as HABApp type and set the return to the mock item
				history_temperatures = []
				for temp_list in test_case.temperatures:
					temp_dict = {"data": []}
					for idx, temp in enumerate(temp_list):
						temp_dict["data"].append({"time": idx * 123456, "state": str(temp)})
					history_temperatures.append(HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData.from_dict(temp_dict))
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

	def test__get_weighted_mean_exception(self):
		"""Test normal function of wighted_mean"""
		with unittest.mock.patch.object(self._summer_winter, "_outside_temp_item", spec=HABApp.openhab.items.NumberItem) as outside_temp_mock, self.assertRaises(habapp_rules.system.summer_winter.SummerWinterException) as context:
			outside_temp_mock.get_persistence_data.return_value = HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData.from_dict({"data": []})
			self._summer_winter._SummerWinter__get_weighted_mean(0)
		self.assertIn("No data for days_in_past = 0 and hour = 7", str(context.exception))

	def test__is_summer(self):
		"""Test if __is_summer method is detecting summer/winter correctly."""
		self._summer_winter._days = 4
		self._summer_winter._temperature_threshold = 16
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
		self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [16, 16, 16, 16.1]
		self.assertTrue(self._summer_winter._SummerWinter__is_summer())

		# check if winter is returned if smaller / equal than threshold
		self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [16, 16, 16, 16.0]
		self.assertFalse(self._summer_winter._SummerWinter__is_summer())

		# check if exceptions are handled correctly (single Exception)
		self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [16, habapp_rules.system.summer_winter.SummerWinterException("not found"), 16.1, 16.0]
		self.assertTrue(self._summer_winter._SummerWinter__is_summer())

		# check if exceptions are handled correctly (3 Exceptions)
		exc = habapp_rules.system.summer_winter.SummerWinterException("not found")
		self._summer_winter._SummerWinter__get_weighted_mean.side_effect = [exc, exc, 16.1, exc]
		with self.assertRaises(habapp_rules.system.summer_winter.SummerWinterException) as context:
			self.assertTrue(self._summer_winter._SummerWinter__is_summer())
		self.assertIn("Not enough values to detect summer/winter. Expected: 4 | actual: 1", str(context.exception))

	def test__is_summer_with_hysteresis(self):
		"""Test summer / winter with hysteresis."""
		TestCase = collections.namedtuple("TestCase", "temperature_values, summer_value, expected_summer")

		test_cases = [
			TestCase([15.5] * 5, None, False),
			TestCase([15.6] * 5, None, False),
			TestCase([16] * 5, None, False),
			TestCase([16.1] * 5, None, True),

			TestCase([15.5] * 5, "OFF", False),
			TestCase([15.6] * 5, "OFF", False),
			TestCase([16] * 5, "OFF", False),
			TestCase([16.1] * 5, "OFF", True),

			TestCase([15.5] * 5, "ON", False),
			TestCase([15.6] * 5, "ON", True),
			TestCase([16] * 5, "ON", True),
			TestCase([16.1] * 5, "ON", True)
		]

		self._summer_winter._SummerWinter__get_weighted_mean = unittest.mock.MagicMock()

		for test_case in test_cases:
			self._summer_winter._SummerWinter__get_weighted_mean.side_effect = test_case.temperature_values
			tests.helper.oh_item.set_state("Unittest_Summer", test_case.summer_value)
			self.assertEqual(test_case.expected_summer, self._summer_winter._SummerWinter__is_summer())

	def test__get_threshold_with_hysteresis(self):
		"""Test getting threshold with hysteresis."""
		TestCase = collections.namedtuple("TestCase", "summer_value, expected_result")

		test_cases = [
			TestCase(None, 16),
			TestCase("ON", 15.5),
			TestCase("OFF", 16)
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Summer", test_case.summer_value)
			self.assertEqual(test_case.expected_result, self._summer_winter._SummerWinter__get_threshold_with_hysteresis(), test_case)

	def test_cb_update_summer(self):
		"""Test correct functionality of summer check callback."""
		with unittest.mock.patch.object(self._summer_winter, "_SummerWinter__is_summer") as is_summer_mock, \
				unittest.mock.patch.object(self._summer_winter, "_item_last_check", spec=HABApp.openhab.items.datetime_item.DatetimeItem) as last_check_mock:
			# switch from winter to summer
			is_summer_mock.return_value = True
			self._summer_winter._cb_update_summer()
			tests.helper.oh_item.assert_value("Unittest_Summer", "ON")
			self.assertEqual(1, last_check_mock.oh_send_command.call_count)

			# already summer (no update should be sent)
			is_summer_mock.return_value = True
			with unittest.mock.patch.object(self._summer_winter, "_item_summer") as summer_item:
				self._summer_winter._cb_update_summer()
				summer_item.send_command.assert_not_called()
				self.assertEqual(2, last_check_mock.oh_send_command.call_count)

			# switch back to winter
			is_summer_mock.return_value = False
			self._summer_winter._cb_update_summer()
			tests.helper.oh_item.assert_value("Unittest_Summer", "OFF")
			self.assertEqual(3, last_check_mock.oh_send_command.call_count)

			# already winter (no update should be sent)
			is_summer_mock.return_value = False
			with unittest.mock.patch.object(self._summer_winter, "_item_summer") as summer_item:
				self._summer_winter._cb_update_summer()
				summer_item.send_command.assert_not_called()
				self.assertEqual(4, last_check_mock.oh_send_command.call_count)

		# exception from __is_summer
		with unittest.mock.patch.object(self._summer_winter, "_SummerWinter__is_summer", side_effect=habapp_rules.system.summer_winter.SummerWinterException("No update")), \
				unittest.mock.patch("habapp_rules.system.summer_winter.LOGGER", spec=logging.Logger) as logger_mock:
			self._summer_winter._cb_update_summer()
			logger_mock.exception.assert_called_once()

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
