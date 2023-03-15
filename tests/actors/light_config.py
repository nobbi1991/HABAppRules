"""Test Light rule."""
import collections
import unittest.mock

import habapp_rules.actors.light_config
import habapp_rules.core.exceptions
import habapp_rules.core.state_machine_rule
import habapp_rules.system
from habapp_rules.actors.light_config import BrightnessTimeout, FunctionConfig, LightConfig


class TestBrightnessTimeout(unittest.TestCase):
	"""Tests for BrightnessTimeout."""

	def test_post_init(self):
		"""Test post init checks."""
		TestCase = collections.namedtuple("TestCase", "value, timeout, valid")

		test_cases = [
			# valid config
			TestCase(100, 1, True),
			TestCase(1, 100, True),
			TestCase(True, 20, True),
			TestCase(False, 0, True),
			TestCase(False, 10, True),
			TestCase(False, 100, True),

			# not valid
			TestCase(100, 0, False),
			TestCase(True, 0, False),
			TestCase(0, 100, False),
		]

		for test_case in test_cases:
			if test_case.valid:
				brightness_timeout = BrightnessTimeout(test_case.value, test_case.timeout)
				self.assertEqual(test_case.value, brightness_timeout.brightness)
				if test_case.value is False:
					if test_case.timeout:
						self.assertEqual(test_case.timeout, brightness_timeout.timeout)
					else:
						self.assertEqual(0.5, brightness_timeout.timeout)
			else:
				with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
					BrightnessTimeout(test_case.value, test_case.timeout)


class TestLightConfig(unittest.TestCase):
	"""Tests for LightConfig."""

	def test_post_init(self):
		"""Test check in post init."""

		TestCase = collections.namedtuple("TestCase", "on, pre_off, leaving, pre_sleep, pre_sleep_prevent, valid")

		func_int = FunctionConfig(day=BrightnessTimeout(80, 3), night=BrightnessTimeout(40, 2), sleeping=BrightnessTimeout(20, 1))
		func_int_partial1 = FunctionConfig(day=None, night=BrightnessTimeout(40, 2), sleeping=BrightnessTimeout(20, 1))
		func_int_partial2 = FunctionConfig(day=BrightnessTimeout(80, 3), night=None, sleeping=BrightnessTimeout(20, 1))
		func_int_partial3 = FunctionConfig(day=BrightnessTimeout(80, 3), night=BrightnessTimeout(40, 2), sleeping=None)
		func_bool = FunctionConfig(day=BrightnessTimeout(True, 3), night=BrightnessTimeout(True, 2), sleeping=BrightnessTimeout(True, 1))

		test_cases = [
			TestCase(on=func_bool, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=True),
			TestCase(on=func_bool, pre_off=func_bool, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=True),
			TestCase(on=func_bool, pre_off=func_bool, leaving=func_bool, pre_sleep=None, pre_sleep_prevent=None, valid=True),
			TestCase(on=func_bool, pre_off=func_bool, leaving=func_bool, pre_sleep=func_bool, pre_sleep_prevent=None, valid=True),

			TestCase(on=func_int, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=True),
			TestCase(on=func_int, pre_off=func_int, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=True),
			TestCase(on=func_int, pre_off=func_int, leaving=func_int, pre_sleep=None, pre_sleep_prevent=None, valid=True),
			TestCase(on=func_int, pre_off=func_int, leaving=func_int, pre_sleep=func_int, pre_sleep_prevent=None, valid=True),

			TestCase(on=None, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
			TestCase(on=None, pre_off=func_bool, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
			TestCase(on=None, pre_off=func_bool, leaving=func_bool, pre_sleep=None, pre_sleep_prevent=None, valid=False),
			TestCase(on=None, pre_off=func_bool, leaving=func_bool, pre_sleep=func_bool, pre_sleep_prevent=None, valid=False),

			TestCase(on=None, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
			TestCase(on=None, pre_off=func_int, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
			TestCase(on=None, pre_off=func_int, leaving=func_int, pre_sleep=None, pre_sleep_prevent=None, valid=False),
			TestCase(on=None, pre_off=func_int, leaving=func_int, pre_sleep=func_int, pre_sleep_prevent=None, valid=False),

			TestCase(on=func_int_partial1, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
			TestCase(on=func_int_partial2, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
			TestCase(on=func_int_partial3, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
		]

		for test_case in test_cases:
			if test_case.valid:
				LightConfig(test_case.on, test_case.pre_off, test_case.leaving, test_case.pre_sleep, test_case.pre_sleep_prevent)
			else:
				with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
					LightConfig(test_case.on, test_case.pre_off, test_case.leaving, test_case.pre_sleep, test_case.pre_sleep_prevent)

	def test_sleep_of_pre_sleep(self):
		"""Test if sleep of pre_sleep is set correctly"""
		light_config = LightConfig(
			on=FunctionConfig(day=BrightnessTimeout(True, 3), night=BrightnessTimeout(True, 2), sleeping=BrightnessTimeout(True, 1)),
			pre_off=None,
			leaving=None,
			pre_sleep=FunctionConfig(day=None, night=None, sleeping=BrightnessTimeout(True, 1))
		)

		self.assertIsNone(light_config.pre_sleep.sleeping)
