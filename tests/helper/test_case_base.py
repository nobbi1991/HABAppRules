"""Common part for tests with simulated OpenHAB items."""
import unittest
import unittest.mock

import tests.helper.oh_item
import tests.helper.rule_runner


class TestCaseBase(unittest.TestCase):
	"""Base class for tests with simulated OpenHAB items."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.send_command_mock_patcher.stop)
		self.send_command_mock = self.send_command_mock_patcher.start()

		self._runner = tests.helper.rule_runner.SimpleRuleRunner()
		self._runner.set_up()

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self._runner.tear_down()
