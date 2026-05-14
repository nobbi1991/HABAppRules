"""Base class for Rule with State Machine."""

import logging
import threading
import typing

import HABApp
import transitions.extensions.states
from HABApp.openhab.items import StringItem
from HABApp.rule import in_thread
from transitions.core import EventData

from habapp_rules.core.exceptions import HabAppRulesError
from habapp_rules.core.logger import InstanceLogger

LOGGER = logging.getLogger(__name__)


class _HabAppTimeout(transitions.extensions.states.Timeout):
    """Timeout state that registers the timer thread with HABApp before processing callbacks.

    threading.Timer fires _process_timeout from an unregistered thread. Wrapping it with
    in_thread prevents HABApp from emitting "Thread usage detected" warnings for every
    timeout-triggered state transition across all state-machine rules.
    """

    def _process_timeout(self, event_data: EventData) -> None:
        in_thread(super()._process_timeout)(event_data)


@transitions.extensions.states.add_state_features(_HabAppTimeout)
class StateMachineWithTimeout(transitions.Machine):
    """State machine class with timeout."""


@transitions.extensions.states.add_state_features(_HabAppTimeout)
class HierarchicalStateMachineWithTimeout(transitions.extensions.HierarchicalMachine):
    """Hierarchical state machine class with timeout."""


class StateMachineRule(HABApp.Rule):
    """Base class for creating rules with a state machine."""

    states: typing.ClassVar[list[dict]] = []
    trans: typing.ClassVar[list[dict]] = []
    state: str
    trigger: typing.Callable[..., bool]
    state_machine: transitions.Machine

    def __init__(self, state_item: StringItem, instance_logger_name: str) -> None:
        """Init rule with state machine.

        Args:
            state_item: name of the item to hold the state
            instance_logger_name: name of the instance logger
        """
        HABApp.Rule.__init__(self)
        self._instance_logger = InstanceLogger(LOGGER, instance_logger_name)
        self._item_state = state_item

    def _get_initial_log_message(self) -> str:
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

    def _post_init(self) -> None:
        """Post init method to initialize the state machine. This should be called at the end of the __init__ method of the child class."""
        self._update_openhab_state()
        self._instance_logger.info(self._get_initial_log_message())

    def _set_state(self, state_name: str) -> None:  # noqa: PLR6301
        """Set given state.

        Args:
            state_name: name of state
        """
        eval(f"self.to_{state_name}()")  # noqa: S307

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item. This should method should be set to "after_state_change" of the state machine."""
        self._item_state.oh_send_command(self.state)

    def _set_state_timeout(self, state_name: str, timeout_value: float) -> None:
        """Set timeout for a given state.

        Args:
            state_name: name of the state
            timeout_value: timeout value in seconds

        Raises:
            HabAppRulesError: if the given state is not a timeout state
        """
        state = self.state_machine.get_state(state_name)

        if not isinstance(state, transitions.extensions.states.Timeout) or not state.on_timeout:
            msg = f"State '{state_name}' is not a timeout state."
            raise HabAppRulesError(msg)

        state.timeout = timeout_value

    def _get_state_timeout(self, state_name: str) -> float:
        """Get current timeout of a state.

        Args:
            state_name: name of the state

        Returns:
            current timeout

        Raises:
            HabAppRulesError: if the given state is not a timeout state
        """
        state = self.state_machine.get_state(state_name)

        if not isinstance(state, transitions.extensions.states.Timeout) or not state.on_timeout:
            msg = f"State '{state_name}' is not a timeout state."
            raise HabAppRulesError(msg)

        return state.timeout

    def on_rule_removed(self) -> None:
        """Override this to implement logic that will be called when the rule has been unloaded."""
        # stop timeout timer of current state
        if hasattr(self, "state_machine") and isinstance(current_state := self.state_machine.get_state(self.state), transitions.extensions.states.Timeout):
            for itm in current_state.runner.values():
                if isinstance(itm, threading.Timer) and itm.is_alive():
                    itm.cancel()
