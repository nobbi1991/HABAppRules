"""Test light HCL rules."""
import collections
import datetime
import unittest.mock

import HABApp

import habapp_rules.actors.light_hcl
import tests.helper.oh_item
import tests.helper.test_case_base


# pylint: disable=protected-access
class TestHclElevation(tests.helper.test_case_base.TestCaseBase):
	"""Tests for elevation-based HCL."""

	def setUp(self):
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Elevation", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Color", None)

		self._config = [
			(-10, 3000),
			(-2, 3800),
			(0, 4200.0),
			(10, 5000)
		]
		self._rule = habapp_rules.actors.light_hcl.HclElevation("Unittest_Elevation", "Unittest_Color", self._config)

	def test_get_sorted_config(self):
		"""Test _get_sorted_config."""
		TestCase = collections.namedtuple("TestCase", "input, output")

		test_cases = [
			TestCase([(-1, 42), (0, 100), (1, 500)], [(-1, 42), (0, 100), (1, 500)]),
			TestCase([(0, 100), (-1, 42), (1, 500)], [(-1, 42), (0, 100), (1, 500)]),
			TestCase([(1, 500), (0, 100), (-1, 42)], [(-1, 42), (0, 100), (1, 500)])
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self.assertEqual(test_case.output, self._rule._get_sorted_config(test_case.input))

	def test_get_hcl_color(self):
		"""Test _get_hcl_color."""

		TestCase = collections.namedtuple("TestCase", "input, output")

		test_cases = [
			TestCase(-20, 3000),
			TestCase(-10.5, 3000),
			TestCase(-10, 3000),
			TestCase(-6, 3400),
			TestCase(-2, 3800),
			TestCase(-1, 4000),
			TestCase(0, 4200),
			TestCase(5, 4600),
			TestCase(10, 5000),
			TestCase(12, 5000)
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self.assertEqual(test_case.output, self._rule._get_hcl_color(test_case.input))

	def test_end_to_end(self):
		"""Test end to end behavior."""
		tests.helper.oh_item.assert_value("Unittest_Color", None)
		tests.helper.oh_item.item_state_change_event("Unittest_Elevation", 0)
		tests.helper.oh_item.assert_value("Unittest_Color", 4200)


# pylint: disable=protected-access
class TestHclTime(tests.helper.test_case_base.TestCaseBase):
	"""Tests for time-based HCL."""

	def setUp(self):
		tests.helper.test_case_base.TestCaseBase.setUp(self)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Color", None)

		self._config = [
			(2, 3000),
			(8, 4000),
			(12, 9000),
			(17, 9000),
			(20, 4000)
		]
		self._rule = habapp_rules.actors.light_hcl.HclTime("Unittest_Color", self._config)

	def test_get_hcl_color(self):
		"""Test _get_hcl_color."""

		TestCase = collections.namedtuple("TestCase", "test_time, output")

		test_cases = [
			TestCase(datetime.datetime(2023, 1, 1, 0, 0), 3333),
			TestCase(datetime.datetime(2023, 1, 1, 1, 0), 3167),
			TestCase(datetime.datetime(2023, 1, 1, 2, 0), 3000),
			TestCase(datetime.datetime(2023, 1, 1, 3, 30), 3250),
			TestCase(datetime.datetime(2023, 1, 1, 5, 0), 3500),
			TestCase(datetime.datetime(2023, 1, 1, 8, 0), 4000),
			TestCase(datetime.datetime(2023, 1, 1, 9, 0), 5250),
			TestCase(datetime.datetime(2023, 1, 1, 12, 0), 9000),
			TestCase(datetime.datetime(2023, 1, 1, 12, 10), 9000),
			TestCase(datetime.datetime(2023, 1, 1, 20, 0), 4000),
			TestCase(datetime.datetime(2023, 1, 1, 22, 0), 3667),
		]

		with unittest.mock.patch("datetime.datetime") as datetime_mock:
			for test_case in test_cases:
				with self.subTest(test_case=test_case):
					datetime_mock.now.return_value = test_case.test_time
					self.assertEqual(test_case.output, round(self._rule._get_hcl_color()))

	def test_update_color(self):
		"""Test _update_color."""
		tests.helper.oh_item.assert_value("Unittest_Color", None)
		with unittest.mock.patch.object(self._rule, "_get_hcl_color", return_value=42):
			self._rule._update_color()
		tests.helper.oh_item.assert_value("Unittest_Color", 42)
