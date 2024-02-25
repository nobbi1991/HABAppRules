"""Test for ventilation config."""
import unittest

import habapp_rules.actors.config.ventilation
import habapp_rules.core.exceptions


class TestVentilationConfig(unittest.TestCase):
	"""Test config class for ventilation"""

	def test_invalid_config(self):
		"""Test invalid config values."""
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.actors.config.ventilation.VentilationConfig(100, long_absence_power_start_time=100)
