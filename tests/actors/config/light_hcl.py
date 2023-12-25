"""Test config for HCL light rules."""
import collections
import unittest.mock

import habapp_rules.actors.config.light_hcl


class TestLightHclConfig(unittest.TestCase):
	"""Test HCL config."""

	def test_sorted_color_config(self):
		"""Test sorting of HCL values."""
		TestCase = collections.namedtuple("TestCase", "input, output")

		test_cases = [
			TestCase([(-1, 42), (0, 100), (1, 500)], [(-1, 42), (0, 100), (1, 500)]),
			TestCase([(0, 100), (-1, 42), (1, 500)], [(-1, 42), (0, 100), (1, 500)]),
			TestCase([(1, 500), (0, 100), (-1, 42)], [(-1, 42), (0, 100), (1, 500)])
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				config = habapp_rules.actors.config.light_hcl.LightHclConfig(test_case.input)
				self.assertEqual(test_case.output, config.color_config)
