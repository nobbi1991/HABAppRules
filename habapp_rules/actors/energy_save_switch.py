"""Energy save switch rules."""

import logging
import typing

from HABApp.openhab.events import ItemCommandEvent, ItemStateChangedEvent, ItemStateUpdatedEvent
from HABApp.openhab.events.event_filters import ItemStateChangedEventFilter

from habapp_rules.actors.config.energy_save_switch import EnergySaveSwitchConfig
from habapp_rules.actors.state_observer import StateObserverSwitch
from habapp_rules.core.state_machine_rule import HierarchicalStateMachineWithTimeout, StateMachineRule
from habapp_rules.system import PresenceState, SleepState

LOGGER = logging.getLogger(__name__)


class EnergySaveSwitch(StateMachineRule):
    """Rules class to manage energy save switches.

    # Items:
    Switch    Switch              "Switch"        {channel="..."}
    Switch    Switch_State        "State"

    # Config:
    config = EnergySaveSwitchConfig(
            items=EnergySaveSwitchItems(
                    switch="Switch",
                    state="Switch_State"
            )
    ))

    # Rule init:
    EnergySaveSwitch(config)
    """

    states: typing.ClassVar = [
        {"name": "Manual"},
        {"name": "Hand", "timeout": 0, "on_timeout": ["_auto_hand_timeout"]},
        {
            "name": "Auto",
            "initial": "Init",
            "children": [
                {"name": "Init"},
                {"name": "On"},
                {"name": "Off"},
                {"name": "WaitCurrent"},
                {"name": "WaitCurrentExtended", "timeout": 0, "on_timeout": ["extended_wait_timeout"]},
            ],
        },
    ]

    trans: typing.ClassVar = [
        # manual
        {"trigger": "manual_on", "source": ["Auto", "Hand"], "dest": "Manual"},
        {"trigger": "manual_off", "source": "Manual", "dest": "Auto"},
        # hand
        {"trigger": "hand_detected", "source": "Auto", "dest": "Hand"},
        {"trigger": "_auto_hand_timeout", "source": "Hand", "dest": "Auto"},
        # sleeping presence conditions
        {"trigger": "on_conditions_met", "source": ["Auto_Off", "Auto_WaitCurrent", "Auto_WaitCurrentExtended"], "dest": "Auto_On"},
        {"trigger": "off_conditions_met", "source": "Auto_On", "dest": "Auto_Off", "unless": "_current_above_threshold"},
        {"trigger": "off_conditions_met", "source": "Auto_On", "dest": "Auto_WaitCurrent", "conditions": "_current_above_threshold"},
        # switch off
        {"trigger": "current_below_threshold", "source": "Auto_WaitCurrent", "dest": "Auto_WaitCurrentExtended"},
        {"trigger": "current_above_threshold", "source": "Auto_WaitCurrentExtended", "dest": "Auto_WaitCurrent"},
        {"trigger": "extended_wait_timeout", "source": "Auto_WaitCurrentExtended", "dest": "Auto_Off"},
        {"trigger": "max_on_countdown", "source": ["Auto_On", "Auto_WaitCurrent", "Hand"], "dest": "Auto_Off"},
    ]

    def __init__(self, config: EnergySaveSwitchConfig) -> None:
        """Init of energy save switch.

        Args:
            config: energy save switch config
        """
        self._config = config
        self._switch_observer = StateObserverSwitch(config.items.switch.name, self._cb_hand, self._cb_hand)

        StateMachineRule.__init__(self, self._config.items.state, self._config.items.switch.name)

        # init state machine
        self._previous_state: str | None = None
        self.state_machine = HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state", initial=self._get_initial_state())

        self._max_on_countdown = self.run.countdown(self._config.parameter.max_on_time, self._cb_max_on_countdown) if self._config.parameter.max_on_time is not None else None  # type:ignore[reportCallIssue]
        self._switch_off_after_external_req = False
        self._set_timeouts()

        # callbacks
        self._config.items.switch.listen_event(self._cb_switch, ItemStateChangedEventFilter())

        if self._config.items.manual is not None:
            self._config.items.manual.listen_event(self._cb_manual, ItemStateChangedEventFilter())
        if self._config.items.presence_state is not None:
            self._config.items.presence_state.listen_event(self._cb_presence_state, ItemStateChangedEventFilter())
        if self._config.items.sleeping_state is not None:
            self._config.items.sleeping_state.listen_event(self._cb_sleeping_state, ItemStateChangedEventFilter())
        if self._config.items.external_request is not None:
            self._config.items.external_request.listen_event(self._cb_external_request, ItemStateChangedEventFilter())
        if self._config.items.current is not None:
            self._config.items.current.listen_event(self._cb_current_changed, ItemStateChangedEventFilter())

        self._post_init()

    def _set_timeouts(self) -> None:
        """Set timeouts."""
        self._set_state_timeout("Hand", self._config.parameter.hand_timeout or 0)
        self._set_state_timeout("Auto_WaitCurrentExtended", self._config.parameter.extended_wait_for_current_time)

    def _get_initial_state(self, default_value: str = "") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
          default_value: default / initial state

        Returns:
          if OpenHAB item has a state it will return it, otherwise return the given default value

        """
        if self._config.items.manual is not None and self._config.items.manual.is_on():
            return "Manual"

        if self._get_on_off_conditions_met():
            return "Auto_On"
        if self._current_above_threshold():
            return "Auto_WaitCurrent"
        return "Auto_Off"

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item and other states.

        This should method should be set to "after_state_change" of the state machine.
        """
        if self.state != self._previous_state:
            super()._update_openhab_state()
            self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

            self._set_switch_state()
            self._previous_state = self.state

    def on_enter_Auto_Init(self) -> None:  # noqa: N802
        """Callback, which is called on enter of init state."""
        if self._get_on_off_conditions_met():
            self.trigger("to_Auto_On")
        else:
            self.trigger("to_Auto_Off")

    def _set_switch_state(self) -> None:
        """Set switch state."""
        if self.state == "Auto_On":
            self._switch_observer.send_command("ON")
        elif self.state == "Auto_Off":
            self._switch_observer.send_command("OFF")

    def _current_above_threshold(self) -> bool:
        """Current is above threshold.

        Returns:
            True if current is above threshold
        """
        if self._config.items.current is None or self._config.items.current.value is None:
            return False

        return self._config.items.current.value > self._config.parameter.current_threshold

    def _get_on_off_conditions_met(self) -> bool:
        """Check if on/off conditions are met.

        Returns:
            True if switch should be ON, else False
        """
        external_req = self._config.items.external_request is not None and self._config.items.external_request.is_on()
        present = self._config.items.presence_state is not None and self._config.items.presence_state == PresenceState.PRESENCE.value
        awake = self._config.items.sleeping_state is not None and self._config.items.sleeping_state == SleepState.AWAKE.value

        return external_req or (present and awake)

    def _conditions_changed(self) -> None:
        """Sleep, presence or external state changed."""
        if self._get_on_off_conditions_met():
            self.trigger("on_conditions_met")
        else:
            self.trigger("off_conditions_met")

    def _cb_max_on_countdown(self) -> None:
        """Callback which is triggered if max on time is reached."""
        if self._max_on_countdown:
            if self._config.items.external_request is not None and self._config.items.external_request.is_on():
                self._switch_off_after_external_req = True
            else:
                self.trigger("max_on_countdown")

    def _cb_switch(self, event: ItemStateChangedEvent) -> None:
        """Callback which is triggered if switch changed.

        Args:
          event: event which triggered this callback
        """
        if self._max_on_countdown is not None:
            if event.value == "ON":
                self._max_on_countdown.reset()
            else:
                self._max_on_countdown.stop()

    def _cb_hand(self, _: ItemStateChangedEvent | ItemCommandEvent | ItemStateUpdatedEvent) -> None:
        """Callback, which is triggered by the state observer if a manual change was detected."""
        self.trigger("hand_detected")

    def _cb_manual(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the manual switch has a state change event.

        Args:
          event: trigger event
        """
        if event.value == "ON":
            self.trigger("manual_on")
        else:
            self.trigger("manual_off")

    def _cb_presence_state(self, _: ItemStateChangedEvent) -> None:
        """Callback which is triggered if presence_state changed."""
        self._conditions_changed()

    def _cb_sleeping_state(self, _: ItemStateChangedEvent) -> None:
        """Callback which is triggered if sleeping state changed."""
        self._conditions_changed()

    def _cb_external_request(self, event: ItemStateChangedEvent) -> None:
        """Callback which is triggered if external request changed."""
        if event.value == "OFF" and self._switch_off_after_external_req:
            self.trigger("to_Auto_Off")
        else:
            self._conditions_changed()
        self._switch_off_after_external_req = False

    def _cb_current_changed(self, _: ItemStateChangedEvent) -> None:
        """Callback which is triggered if the current value changed."""
        if self.state == "Auto_WaitCurrent" and not self._current_above_threshold():
            self.trigger("current_below_threshold")

        if self.state == "Auto_WaitCurrentExtended" and self._current_above_threshold():
            self.trigger("current_above_threshold")
