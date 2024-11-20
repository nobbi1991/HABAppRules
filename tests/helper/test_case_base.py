"""Common part for tests with simulated OpenHAB items."""

import threading
import unittest
import unittest.mock

import habapp_rules.core.state_machine_rule
import tests.helper.oh_item
import tests.helper.rule_runner


class TestCaseBase(unittest.TestCase):
    """Base class for tests with simulated OpenHAB items."""

    def setUp(self) -> None:
        """Setup test case."""
        self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
        self.addCleanup(self.send_command_mock_patcher.stop)
        self.send_command_mock = self.send_command_mock_patcher.start()

        self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.post_update", new=tests.helper.oh_item.set_state)
        self.addCleanup(self.send_command_mock_patcher.stop)
        self.send_command_mock = self.send_command_mock_patcher.start()

        self.item_exists_mock_patcher = unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", return_value=True)
        self.addCleanup(self.item_exists_mock_patcher.stop)
        self.item_exists_mock = self.item_exists_mock_patcher.start()

        self._runner = tests.helper.rule_runner.SimpleRuleRunner()
        self._runner.set_up()

    def tearDown(self) -> None:
        """Tear down test case."""
        tests.helper.oh_item.remove_all_mocked_items()
        self._runner.tear_down()


class TestCaseBaseStateMachine(TestCaseBase):
    """Base class for tests with simulated OpenHAB items and state machines."""

    def setUp(self) -> None:
        """Setup tests."""
        TestCaseBase.setUp(self)

        self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
        self.addCleanup(self.transitions_timer_mock_patcher.stop)
        self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

        self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
        self.addCleanup(self.threading_timer_mock_patcher.stop)
        self.threading_timer_mock = self.threading_timer_mock_patcher.start()

        self.on_rule_removed_mock_patcher = unittest.mock.patch("habapp_rules.core.state_machine_rule.StateMachineRule.on_rule_removed", spec=habapp_rules.core.state_machine_rule.StateMachineRule.on_rule_removed)
        self.addCleanup(self.on_rule_removed_mock_patcher.stop)
        self.on_rule_removed_mock_patcher.start()

    def _get_state_names(self, states: dict, parent_state: str | None = None) -> list[str]:  # pragma: no cover
        """Helper function to get all state names (also nested states).

        Args:
            states: dict of all states or children states
            parent_state: name of parent state, only if it is a nested state machine

        Returns:
            list of all state names
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
