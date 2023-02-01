"""Test Light rule."""
import collections
import unittest.mock

import habapp_rules.actors.light_config
import habapp_rules.common.exceptions
import habapp_rules.common.exceptions
import habapp_rules.common.state_machine_rule
import habapp_rules.system


class TestBrightnessTimeoutConfig(unittest.TestCase):
	"""Test cases for BrightnessTimeoutConfig."""

	def test_post_init(self):
		"""Test check in post init."""
		TestCase = collections.namedtuple("TestCase", "value_day, value_night, value_sleeping, timeout_day, timeout_night, timeout_sleeping, error")

		test_cases = [
			# supported configs
			TestCase(80, 80, 80, 1, 1, 1, False),
			TestCase(0, 0, 0, 1, 1, 1, False),
			TestCase(True, True, True, 1, 1, 1, False),
			TestCase(False, False, False, 1, 1, 1, False),
			TestCase(None, None, None, 1, 1, 1, False),

			# not supported type of value
			TestCase("ON", None, None, 1, 1, 1, True),
			TestCase(None, [None], None, 1, 1, 1, True),
			TestCase(None, None, {"state": None}, 1, 1, 1, True),

			# timeout zero
			TestCase(True, True, True, 0, 1, 1, True),
			TestCase(True, True, True, 1, 0, 1, True),
			TestCase(True, True, True, 1, 1, 0, True),

			# wrong timeout_type
			TestCase(True, True, True, "0", 1, 1, True),
			TestCase(True, True, True, 1, [0], 1, True),
			TestCase(True, True, True, 1, 1, {"value:": 0}, True),
		]

		for test_case in test_cases:
			if test_case.error:
				with self.assertRaises(habapp_rules.common.exceptions.HabAppRulesConfigurationException):
					habapp_rules.actors.light_config.BrightnessTimeoutConfig(test_case.value_day, test_case.timeout_day, test_case.value_night, test_case.timeout_night, test_case.value_sleeping, test_case.timeout_sleeping)
			else:
				habapp_rules.actors.light_config.BrightnessTimeoutConfig(test_case.value_day, test_case.timeout_day, test_case.value_night, test_case.timeout_night, test_case.value_sleeping, test_case.timeout_sleeping)

	def test_str(self):
		"""Test correct string representation."""
		state_config = habapp_rules.actors.light_config.BrightnessTimeoutConfig(100, 11, 42, 22, 20, 33)

		expected_result = f"BrightnessTimeoutConfig\nday: 100 | 11s\nnight: 42 | 22s\nsleeping: 20 | 33s\n"
		self.assertEqual(state_config.__str__(), state_config.__repr__())
		self.assertEqual(expected_result, str(state_config))


class TestLightConfig(unittest.TestCase):
	"""Tests for LightConfig."""

	def test_post_init(self):
		TestCase = collections.namedtuple("TestCase", "on, pre_off, leaving, pre_sleep, pre_sleep_prevent, error")

		config_on = habapp_rules.actors.light_config.BrightnessTimeoutConfig(True, 1, True, 2, True, 3)
		config_off = habapp_rules.actors.light_config.BrightnessTimeoutConfig(False, 1, False, 2, False, 3)
		config_none = habapp_rules.actors.light_config.BrightnessTimeoutConfig(None, 1, None, 1, None, 3)

		test_cases = [
			# ok
			TestCase(config_on, config_on, config_on, config_on, None, False),
			TestCase(config_on, config_off, config_off, config_off, None, False),
			TestCase(config_on, config_none, config_none, config_none, None, False),
			TestCase(config_on, None, None, None, None, False),

			# not ok
			TestCase(None, config_on, config_on, config_on, None, True),  # 'on' can not be set to None
			TestCase(config_off, config_on, config_on, config_on, None, True),  # brightness of 'on' can not be set to off
			TestCase(config_none, config_on, config_on, config_on, None, True),  # brightness of 'on' can not be set to None
			TestCase("State", config_on, config_on, config_on, None, True),  # wrong type
			TestCase(config_on, "State", config_on, config_on, None, True),  # wrong type
			TestCase(config_on, config_on, "State", config_on, None, True),  # wrong type
			TestCase(config_on, config_on, config_on, "State", None, True),  # wrong type
		]

		for test_case in test_cases:
			if test_case.error:
				with self.assertRaises(habapp_rules.common.exceptions.HabAppRulesConfigurationException):
					habapp_rules.actors.light_config.LightConfigBak(test_case.on, test_case.pre_off, test_case.leaving, test_case.pre_sleep, test_case.pre_sleep_prevent)
			else:
				habapp_rules.actors.light_config.LightConfigBak(test_case.on, test_case.pre_off, test_case.leaving, test_case.pre_sleep, test_case.pre_sleep_prevent)
