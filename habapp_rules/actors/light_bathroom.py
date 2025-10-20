"""Bathroom light rules."""

import logging
import time
import typing

import HABApp

import habapp_rules.actors.config.light_bathroom
import habapp_rules.actors.state_observer
import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system

LOGGER = logging.getLogger(__name__)


class BathroomLight(habapp_rules.core.state_machine_rule.StateMachineRule):
    """Bathroom light rule."""

    states: typing.ClassVar = [
        {"name": "Manual"},
        {
            "name": "Auto",
            "initial": "Init",
            "children": [
                {"name": "Init"},
                {"name": "Off"},
                {"name": "On", "initial": "Init", "children": [{"name": "Init"}, {"name": "MainDay"}, {"name": "MainNight"}, {"name": "MainAndMirror"}]},
            ],
        },
    ]

    trans: typing.ClassVar = [
        # manual
        {"trigger": "manual_on", "source": "Auto", "dest": "Manual"},
        {"trigger": "manual_off", "source": "Manual", "dest": "Auto"},
        # switch on
        {"trigger": "hand_on", "source": "Auto_Off", "dest": "Auto_On"},
        # mirror
        {"trigger": "mirror_on", "source": ["Auto_On_MainDay", "Auto_On_MainNight"], "dest": "Auto_On_MainAndMirror"},
        {"trigger": "mirror_off", "source": "Auto_On_MainAndMirror", "dest": "Auto_On_MainDay", "conditions": "_is_day"},
        {"trigger": "mirror_off", "source": "Auto_On_MainAndMirror", "dest": "Auto_On_MainNight", "unless": "_is_day"},
        # off
        {"trigger": "hand_off", "source": "Auto_On", "dest": "Auto_Off"},
        {"trigger": "sleep_started", "source": "Auto_On", "dest": "Auto_Off"},
        {"trigger": "leaving", "source": "Auto_On", "dest": "Auto_Off"},
    ]

    def __init__(self, config: habapp_rules.actors.config.light_bathroom.BathroomLightConfig) -> None:
        """Init rule.

        Args:
            config: Config of bathroom light rule
        """
        self._config = config
        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.light_main.name)

        self._sleep_end_time = 0
        self._switch_on_via_increase = False
        control_names = [self._config.items.light_main_ctr.name] if self._config.items.light_main_ctr is not None else []
        self._light_main_observer = habapp_rules.actors.state_observer.StateObserverDimmer(self._config.items.light_main.name, control_names=control_names, cb_on=self._cb_hand_on, cb_off=self._cb_hand_off, value_tolerance=5)

        # init state machine
        self._previous_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_state(self._get_initial_state())

        # callbacks
        self._config.items.manual.listen_event(self._cb_manual, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.light_mirror.listen_event(self._cb_mirror, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.sleeping_state.listen_event(self._cb_sleeping_state, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.presence_state.listen_event(self._cb_presence_state, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _get_initial_state(self, default_value: str = "initial") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        return "Manual" if self._config.items.manual.is_on() else "Auto"

    def on_enter_Auto_Init(self) -> None:  # noqa: N802
        """Callback, which is called on enter of Auto_Init state."""
        if self._config.items.light_main.is_on():
            self.to_Auto_On()
        else:
            self.to_Auto_Off()

    def on_enter_Auto_On_Init(self) -> None:  # noqa: N802
        """Callback, which is called on enter of Auto_On_Init state."""
        if self._mirror_is_on():
            self.to_Auto_On_MainAndMirror()
        elif self._is_day():
            self.to_Auto_On_MainDay()
        else:
            self.to_Auto_On_MainNight()

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item and other states.

        This should method should be set to "after_state_change" of the state machine.
        """
        if self.state != self._previous_state:
            super()._update_openhab_state()
            self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

            self._set_outputs()
            self._previous_state = self.state

    def _set_outputs(self) -> None:
        """Set outputs to OpenHAB items."""
        if self.state == "Manual":
            self._switch_on_via_increase = False
            return

        if self.state == "Auto_Off":
            habapp_rules.core.helper.send_if_different(self._config.items.light_mirror, "OFF")
            if self._light_main_observer.value:
                self._light_main_observer.send_command(0)
        elif self.state == "Auto_On_MainDay":
            habapp_rules.core.helper.send_if_different(self._config.items.light_main_hcl, "ON")
        elif self.state == "Auto_On_MainNight":
            if not self._switch_on_via_increase:
                extended_sleep_brightness = self._config.parameter.brightness_night_extended or self._config.parameter.brightness_night
                target_brightness = extended_sleep_brightness if self._is_extended_sleep() else self._config.parameter.brightness_night
                self._light_main_observer.send_command(target_brightness)
            habapp_rules.core.helper.send_if_different(self._config.items.light_main_color, self._config.parameter.color_night)
        elif self.state == "Auto_On_MainAndMirror":
            habapp_rules.core.helper.send_if_different(self._config.items.light_main_color, self._config.parameter.color_mirror_sync)
            new_brightness = max(self._config.parameter.min_brightness_mirror_sync, self._light_main_observer.value)
            self._light_main_observer.send_command(new_brightness)

        self._switch_on_via_increase = False

    def _is_day(self) -> bool:
        """Check if it is day.

        Returns:
            True if it is day
        """
        if self._config.items.sleeping_state.value != habapp_rules.system.SleepState.AWAKE.value:
            return False

        return time.time() - self._sleep_end_time > self._config.parameter.extended_sleep_time

    def _is_extended_sleep(self) -> bool:
        """Check if it is extended sleep.

        Returns:
            True if it is extended sleep
        """
        return time.time() - self._sleep_end_time <= self._config.parameter.extended_sleep_time

    def _mirror_is_on(self) -> bool:
        """Check if mirror light is on.

        Returns:
            True if mirror light is on
        """
        return self._config.items.light_mirror.is_on()

    def _cb_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if the 'manual' item changed.

        Args:
            event: event, which triggered this callback
        """
        if event.value == "ON":
            self.manual_on()
        else:
            self.manual_off()

    def _cb_hand_on(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if a hand action was detected.

        Args:
            event: event, which triggered this callback
        """
        self._switch_on_via_increase = event.value == "INCREASE"
        self.hand_on()

    def _cb_hand_off(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa: ARG002
        self.hand_off()

    def _cb_mirror(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa: ARG002
        if self._config.items.light_mirror.is_on():
            self.mirror_on()
        else:
            self.mirror_off()

    def _cb_sleeping_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        if event.value == habapp_rules.system.SleepState.PRE_SLEEPING.value:
            self.sleep_started()

        if event.value == habapp_rules.system.SleepState.AWAKE.value:
            self._sleep_end_time = time.time()

    def _cb_presence_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        if event.value == habapp_rules.system.PresenceState.LEAVING.value:
            self.leaving()
