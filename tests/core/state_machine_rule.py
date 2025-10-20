"""Unit-test for state_machine."""

import collections
import time
import unittest.mock

import HABApp.openhab.items.switch_item

import habapp_rules.core.state_machine_rule
import tests.helper.oh_item
import tests.helper.test_case_base


class TestStateMachineRule(tests.helper.test_case_base.TestCaseBase):
    """Tests for StateMachineRule."""

    def setUp(self) -> None:
        """Setup unit-tests."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_State", None)
        self.state_item = HABApp.openhab.items.StringItem.get_item("Unittest_State")

        self.item_exists_mock.return_value = False

        with unittest.mock.patch("habapp_rules.core.helper.create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_common_state_machine_rule_StateMachineRule_state", "")):
            self._state_machine = habapp_rules.core.state_machine_rule.StateMachineRule(self.state_item)

    def test_get_initial_state(self) -> None:
        """Test getting of initial state."""
        TestCase = collections.namedtuple("TestCase", "item_value, state_names, default, expected_result")
        test_cases = [
            TestCase("state1", ["state1", "state2"], "default", "state1"),
            TestCase("wrong_state", ["state1", "state2"], "default", "default"),
            TestCase("state1", ["new_state1", "new_state_2"], "default", "default"),
            TestCase("state1", [], "default", "default"),
        ]

        with unittest.mock.patch.object(self._state_machine, "_item_state") as state_item_mock:
            for test_case in test_cases:
                state_item_mock.value = test_case.item_value
                self._state_machine.states = [{"name": name} for name in test_case.state_names]
                self.assertEqual(self._state_machine._get_initial_state(test_case.default), test_case.expected_result)

    def test_update_openhab_state(self) -> None:
        """Test if OpenHAB state will be updated."""
        self._state_machine.state = "some_state"
        with unittest.mock.patch.object(self._state_machine, "_item_state") as state_item:
            self._state_machine._update_openhab_state()
            state_item.oh_send_command.assert_called_once_with("some_state")

    def test_on_rule_removed(self) -> None:
        """Test on_rule_removed."""
        # check if 'on_rule_removed' is still available in HABApp
        self.assertIsNotNone(HABApp.rule.Rule.on_rule_removed)

        # check if timer is stopped correctly
        states = [{"name": "stopped"}, {"name": "running", "timeout": 99, "on_timeout": "trigger_stop"}]

        with unittest.mock.patch("habapp_rules.core.helper.create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_common_state_machine_rule_StateMachineRule_state", "")):
            for initial_state in ["stopped", "running"]:
                state_machine_rule = habapp_rules.core.state_machine_rule.StateMachineRule(self.state_item)

                state_machine_rule.state_machine = habapp_rules.core.state_machine_rule.StateMachineWithTimeout(model=state_machine_rule, states=states, ignore_invalid_triggers=True)

                state_machine_rule._set_state(initial_state)

                if initial_state == "running":
                    self.assertTrue(next(iter(state_machine_rule.state_machine.states["running"].runner.values())).is_alive())

                state_machine_rule.on_rule_removed()

                if initial_state == "running":
                    time.sleep(0.001)
                    self.assertFalse(next(iter(state_machine_rule.state_machine.states["running"].runner.values())).is_alive())
