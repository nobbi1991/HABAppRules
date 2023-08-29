"""Test config for light rules."""
import collections
import unittest.mock

import habapp_rules.actors.config.shading
import habapp_rules.core.exceptions


class ShadingConfig(unittest.TestCase):
	"""Tests for shading config."""

	def test_post_init(self):
		"""Test __post_init"""
		TestCase = collections.namedtuple("TestCase", "door_post_time_input, door_post_time_expected")

		test_cases = [
			TestCase(None, 1),
			TestCase(0, 1),
			TestCase(1, 1),
			TestCase(100, 100)
		]

		for test_case in test_cases:
			config = habapp_rules.actors.config.shading.ShadingConfig(
				habapp_rules.actors.config.shading.ShadingPosition(100, 100),
				door_post_time=test_case.door_post_time_input
			)
			self.assertEqual(test_case.door_post_time_expected, config.door_post_time)
