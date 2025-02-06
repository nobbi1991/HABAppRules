"""Base class for Rule with State Machine."""

import threading
import typing

import HABApp
import HABApp.openhab.connection.handler.func_sync
import transitions.extensions.states


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class StateMachineWithTimeout(transitions.Machine):
    """State machine class with timeout."""


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class HierarchicalStateMachineWithTimeout(transitions.extensions.HierarchicalMachine):
    """Hierarchical state machine class with timeout."""


class StateMachineRule(HABApp.Rule):
    """Base class for creating rules with a state machine."""

    states: typing.ClassVar[list[dict]] = []
    trans: typing.ClassVar[list[dict]] = []
    state: str

    def __init__(self, state_item: HABApp.openhab.items.StringItem) -> None:
        """Init rule with state machine.

        Args:
            state_item: name of the item to hold the state
        """
        self.state_machine: transitions.Machine | None = None
        HABApp.Rule.__init__(self)

        self._item_state = state_item

    def get_initial_log_message(self) -> str:
        """Get log message which can be logged at the init of a rule with a state machine.

        Returns:
            log message
        """
        return f"Init of rule '{self.__class__.__name__}' with name '{self.rule_name}' was successful. Initial state = '{self.state}' | State item = '{self._item_state.name}'"

    def _get_initial_state(self, default_value: str = "initial") -> str:
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        if self._item_state.value and self._item_state.value in [item.get("name", None) for item in self.states if isinstance(item, dict)]:
            return self._item_state.value
        return default_value

    def _set_initial_state(self) -> None:
        """Set initial state.

        if the ``initial_state`` parameter of the state machine constructor is used the timeouts will not be started for the initial state.
        """
        self._set_state(self._get_initial_state())

    def _set_state(self, state_name: str) -> None:  # noqa: PLR6301
        """Set given state.

        Args:
            state_name: name of state
        """
        eval(f"self.to_{state_name}()")  # noqa: S307

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item. This should method should be set to "after_state_change" of the state machine."""
        self._item_state.oh_send_command(self.state)

    def on_rule_removed(self) -> None:
        """Override this to implement logic that will be called when the rule has been unloaded."""
        # stop timeout timer of current state
        if self.state_machine:
            for itm in self.state_machine.get_state(self.state).runner.values():
                if isinstance(itm, threading.Timer) and itm.is_alive():
                    itm.cancel()
