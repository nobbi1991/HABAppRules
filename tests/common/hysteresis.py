"""Test for hysteresis switch."""
import collections
import unittest

import habapp_rules.common.hysteresis


# pylint: disable=protected-access
class TestHysteresis(unittest.TestCase):
	"""Tests for HysteresisSwitch."""

	def setUp(self):
		"""Setup for all test cases."""
		self.hysteresis_switch = habapp_rules.common.hysteresis.HysteresisSwitch(42, 2)
		self.hysteresis_switch_on_off = habapp_rules.common.hysteresis.HysteresisSwitch(42, 2, False)

	def test_get_output(self):
		"""test get_output"""
		TestCase = collections.namedtuple("TestCase", "threshold, hysteresis, state, value, expected_result")

		test_cases = [
			# hysteresis = 1, current_state = False
			TestCase(10, 1, False, 9, False),
			TestCase(10, 1, False, 9.4, False),
			TestCase(10, 1, False, 9.5, False),
			TestCase(10, 1, False, 9.6, False),
			TestCase(10, 1, False, 10.4, False),
			TestCase(10, 1, False, 10.5, True),
			TestCase(10, 1, False, 10.5, True),

			# hysteresis = 1, current_state = True
			TestCase(10, 1, True, 9, False),
			TestCase(10, 1, True, 9.4, False),
			TestCase(10, 1, True, 9.5, True),
			TestCase(10, 1, True, 9.6, True),
			TestCase(10, 1, True, 10.4, True),
			TestCase(10, 1, True, 10.5, True),
			TestCase(10, 1, True, 10.5, True),

			# hysteresis = 4, current_state = False
			TestCase(42, 4, False, 39.9, False),
			TestCase(42, 4, False, 40, False),
			TestCase(42, 4, False, 40.1, False),
			TestCase(42, 4, False, 42, False),
			TestCase(42, 4, False, 43.9, False),
			TestCase(42, 4, False, 44, True),
			TestCase(42, 4, False, 44.1, True),

			# hysteresis = 4, current_state = True
			TestCase(42, 4, True, 39.9, False),
			TestCase(42, 4, True, 40, True),
			TestCase(42, 4, True, 40.1, True),
			TestCase(42, 4, True, 42, True),
			TestCase(42, 4, True, 43.9, True),
			TestCase(42, 4, True, 44, True),
			TestCase(42, 4, True, 44.1, True),
		]

		for test_case in test_cases:
			self.hysteresis_switch._threshold = test_case.threshold
			self.hysteresis_switch._hysteresis = test_case.hysteresis
			self.hysteresis_switch._on_off_state = test_case.state
			self.hysteresis_switch_on_off._threshold = test_case.threshold
			self.hysteresis_switch_on_off._hysteresis = test_case.hysteresis
			self.hysteresis_switch_on_off._on_off_state = test_case.state

			self.assertEqual(test_case.expected_result, self.hysteresis_switch.get_output(test_case.value))
			self.assertEqual("ON" if test_case.expected_result else "OFF", self.hysteresis_switch_on_off.get_output(test_case.value))

			self.assertEqual(test_case.expected_result, self.hysteresis_switch._on_off_state)
			self.assertEqual(test_case.expected_result, self.hysteresis_switch_on_off._on_off_state)

	def test_set_threshold(self):
		"""test set_threshold."""

		self.assertEqual(42, self.hysteresis_switch._threshold)
		self.assertEqual(42, self.hysteresis_switch_on_off._threshold)

		self.hysteresis_switch.set_threshold_on(83)
		self.hysteresis_switch_on_off.set_threshold_on(83)

		self.assertEqual(83, self.hysteresis_switch._threshold)
		self.assertEqual(83, self.hysteresis_switch_on_off._threshold)
