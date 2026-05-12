"""Common part for tests with simulated OpenHAB items."""

import threading
import unittest
import unittest.mock

from HABApp.core.internals import get_current_context
from HABApp.rule.rule import Rule

from tests.helper.async_helper import call_async_sync
from tests.helper.oh_item import oh_post_update, oh_send_command, remove_all_mocked_items
from tests.helper.rule_runner import SimpleRuleRunner


class TestCaseBase(unittest.TestCase):
    """Base class for tests with simulated OpenHAB items."""

    def setUp(self) -> None:
        """Setup test case."""
        self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.OpenhabItem.oh_send_command", new=oh_send_command)
        self.addCleanup(self.send_command_mock_patcher.stop)
        self.send_command_mock = self.send_command_mock_patcher.start()

        self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.OpenhabItem.oh_post_update", new=oh_post_update)
        self.addCleanup(self.send_command_mock_patcher.stop)
        self.send_command_mock = self.send_command_mock_patcher.start()

        self.item_exists_mock_patcher = unittest.mock.patch("habapp_rules.core.helper.item_exists", return_value=True)
        self.addCleanup(self.item_exists_mock_patcher.stop)
        self.item_exists_mock = self.item_exists_mock_patcher.start()

        self._runner = SimpleRuleRunner()
        call_async_sync(self._runner.set_up)

    def unload_rule(self, rule: Rule) -> None:
        """Unload a rule.

        Args:
            rule: The rule to unload
        """
        call_async_sync(get_current_context(rule).unload_rule)
        self._runner.loaded_rules.remove(rule)

    def tearDown(self) -> None:
        """Tear down test case."""
        remove_all_mocked_items()
        call_async_sync(self._runner.tear_down)


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

        self.on_rule_removed_mock_patcher = unittest.mock.patch("habapp_rules.core.state_machine_rule.StateMachineRule.on_rule_removed", new_callable=unittest.mock.AsyncMock)
        self.addCleanup(self.on_rule_removed_mock_patcher.stop)
        self.on_rule_removed_mock_patcher.start()
