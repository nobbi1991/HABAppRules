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

	def _get_state_names(self, states: dict, parent_state: str | None = None) -> list[str]:  # pragma: no cover
		"""Helper function to get all state names (also nested states)

		:param states: dict of all states or children states
		:param parent_state: name of parent state, only if it is a nested state machine
		:return: list of all state names
		"""
		state_names = []
		prefix = f"{parent_state}_" if parent_state else ""
		if parent_state:
			states = states["children"]

		for state in states:
			if "children" in state:
				state_names += self._get_state_names(state, state["name"])
			else:
				state_names.append(f"{prefix}{state['name']}")
		return state_names
