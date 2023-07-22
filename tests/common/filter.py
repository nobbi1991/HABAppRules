"""Unit-test for filter functions / rules."""
import collections
import unittest.mock

import HABApp

import habapp_rules.common.filter
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.test_case_base


# pylint: disable=protected-access
class TestExponentialFilter(tests.helper.test_case_base.TestCaseBase):
	"""Tests ExponentialFilter."""

	def setUp(self) -> None:
		"""Setup unit-tests."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Raw", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Filtered", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Filtered_2", 0)

		self._rule_run_mock = unittest.mock.MagicMock()
		with unittest.mock.patch("HABApp.rule.rule._HABAppSchedulerView", return_value=self._rule_run_mock):
			self.filter = habapp_rules.common.filter.ExponentialFilter("Unittest_Raw", "Unittest_Filtered", 10)
			self.filter_increase = habapp_rules.common.filter.ExponentialFilter("Unittest_Raw", "Unittest_Filtered_2", 100, True)

	def test__init__(self):
		"""Test __init__."""
		self._rule_run_mock.every.assert_has_calls([  # check if self.run.every was called
			unittest.mock.call(None, 2.0, self.filter._cb_cyclic_calculate_and_update_output),
			unittest.mock.call(None, 20.0, self.filter_increase._cb_cyclic_calculate_and_update_output)
		])

		self.assertEqual("Unittest_Raw", self.filter._item_raw.name)
		self.assertEqual("Unittest_Raw", self.filter_increase._item_raw.name)

		self.assertEqual("Unittest_Filtered", self.filter._item_filtered.name)
		self.assertEqual("Unittest_Filtered_2", self.filter_increase._item_filtered.name)

		self.assertEqual(0.2, self.filter._alpha)
		self.assertEqual(0.2, self.filter_increase._alpha)

		self.assertFalse(self.filter._instant_increase)
		self.assertFalse(self.filter._instant_decrease)

		self.assertTrue(self.filter_increase._instant_increase)
		self.assertFalse(self.filter_increase._instant_decrease)

		# instant_increase and instant_decrease is set
		logger_mock = unittest.mock.MagicMock()
		with unittest.mock.patch("habapp_rules.core.logger.InstanceLogger", return_value=logger_mock):
			self.filter = habapp_rules.common.filter.ExponentialFilter("Unittest_Raw", "Unittest_Filtered", 10, True, True)
		logger_mock.warning.assert_called_once_with("instant_increase and instant_decrease was set to True. This deactivates the filter completely!")

	def test_cb_cyclic_calculate_and_update_output(self):
		"""Test _cb_cyclic_calculate_and_update_output."""
		TestCase = collections.namedtuple("TestCase", "new_value, previous_value, expected_result")

		test_cases = [
			TestCase(1, 1, 1),
			TestCase(2, 1, 1.2),
			TestCase(2, 0, 0.4),
			TestCase(0, 2, 1.6),
			TestCase(None, None, 999),
			TestCase(None, 42, 999),
			TestCase(42, None, 999),
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Raw", test_case.new_value)
			tests.helper.oh_item.set_state("Unittest_Filtered", 999)  # set some random value
			self.filter._previous_value = test_case.previous_value

			self.filter._cb_cyclic_calculate_and_update_output()

			self.assertEqual(test_case.expected_result, round(self.filter._item_filtered.value, 2))

			if test_case.new_value is not None and test_case.previous_value is not None:
				self.assertEqual(test_case.expected_result, round(self.filter._previous_value, 2))
			else:
				self.assertEqual(test_case.previous_value, self.filter._previous_value)

	def test_cb_item_raw(self):
		"""Test _cb_item_raw."""
		TestCase = collections.namedtuple("TestCase", "new_value, instant_increase, instant_decrease, expected_value")

		test_cases = [
			TestCase(200, False, False, 100),
			TestCase(200, False, True, 100),
			TestCase(200, True, False, 200),

			TestCase(50, False, False, 100),
			TestCase(50, False, True, 50),
			TestCase(50, True, False, 100),
		]

		for test_case in test_cases:
			tests.helper.oh_item.set_state("Unittest_Filtered_2", 100)  # set some random value
			self.filter_increase._previous_value = 100
			self.filter_increase._instant_increase = test_case.instant_increase
			self.filter_increase._instant_decrease = test_case.instant_decrease

			tests.helper.oh_item.item_state_change_event("Unittest_Raw", test_case.new_value)

			tests.helper.oh_item.assert_value("Unittest_Filtered_2", test_case.expected_value)
