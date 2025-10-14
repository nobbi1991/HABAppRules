"""Rules to manage lights."""

from __future__ import annotations

import abc
import copy
import logging
import math
import threading
import time
import typing

import HABApp.openhab.events
import HABApp.openhab.items

import habapp_rules.actors.config.light
import habapp_rules.actors.state_observer
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system

if typing.TYPE_CHECKING:
    from collections.abc import Callable  # pragma: no cover

LOGGER = logging.getLogger(__name__)

DIMMER_VALUE_TOLERANCE = 5
MINUTE_IN_SEC = 60


class _LightBase(habapp_rules.core.state_machine_rule.StateMachineRule, abc.ABC):
    """Base class for lights."""

    states: typing.ClassVar = [
        {"name": "manual"},
        {
            "name": "auto",
            "initial": "init",
            "children": [
                {"name": "init"},
                {"name": "on", "timeout": 10, "on_timeout": "auto_on_timeout"},
                {"name": "preoff", "timeout": 4, "on_timeout": "preoff_timeout"},
                {"name": "off"},
                {"name": "leaving", "timeout": 5, "on_timeout": "leaving_timeout"},
                {"name": "presleep", "timeout": 5, "on_timeout": "presleep_timeout"},
                {"name": "restoreState"},
            ],
        },
    ]

    trans: typing.ClassVar = [
        {"trigger": "manual_on", "source": "auto", "dest": "manual"},
        {"trigger": "manual_off", "source": "manual", "dest": "auto"},
        {"trigger": "hand_on", "source": ["auto_off", "auto_preoff"], "dest": "auto_on"},
        {"trigger": "hand_off", "source": ["auto_on", "auto_leaving", "auto_presleep"], "dest": "auto_off"},
        {"trigger": "hand_off", "source": "auto_preoff", "dest": "auto_on"},
        {"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
        {"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_off", "unless": "_pre_off_configured"},
        {"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
        {"trigger": "leaving_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
        {"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_restoreState"},
        {"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
        {"trigger": "sleep_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"},
        {"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_restoreState"},
        {"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"},
    ]
    _state_observer: habapp_rules.actors.state_observer.StateObserverSwitch | habapp_rules.actors.state_observer.StateObserverDimmer

    def __init__(self, config: habapp_rules.actors.config.light.LightConfig) -> None:
        """Init of basic light object.

        Args:
            config: light config
        """
        self._config = config

        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.light.name)

        # init state machine
        self._previous_state = None
        self._restore_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")

        self._brightness_before = -1
        self._timeout_on = 0
        self._timeout_pre_off = 0
        self._timeout_pre_sleep = 0
        self._timeout_leaving = 0
        self.__time_sleep_start = 0
        self._set_timeouts()
        self._set_initial_state()

        # callbacks
        self._config.items.manual.listen_event(self._cb_manu, HABApp.openhab.events.ItemStateUpdatedEventFilter())
        if self._config.items.sleeping_state is not None:
            self._config.items.sleeping_state.listen_event(self._cb_sleeping, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.presence_state is not None:
            self._config.items.presence_state.listen_event(self._cb_presence, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.day.listen_event(self._cb_day, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._update_openhab_state()
        self._instance_logger.debug(super().get_initial_log_message())

    def _get_initial_state(self, default_value: str = "") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
             OpenHAB item has a state it will return it, otherwise return the given default value
        """
        if self._config.items.manual.is_on():
            return "manual"
        if self._config.items.light.is_on():
            if (
                self._config.items.presence_state is not None
                and self._config.items.presence_state.value == habapp_rules.system.PresenceState.PRESENCE.value
                and getattr(self._config.items.sleeping_state, "value", "awake") in {habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.SleepState.LOCKED.value}
            ):
                return "auto_on"
            if (
                self._pre_sleep_configured()
                and self._config.items.presence_state is not None
                and self._config.items.presence_state.value in {habapp_rules.system.PresenceState.PRESENCE.value, habapp_rules.system.PresenceState.LEAVING.value}
                and getattr(self._config.items.sleeping_state, "value", "") in {habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value}
            ):
                return "auto_presleep"
            if self._leaving_configured():
                return "auto_leaving"
            return "auto_on"
        return "auto_off"

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item and other states.

        This should method should be set to "after_state_change" of the state machine.
        """
        if self.state != self._previous_state:
            super()._update_openhab_state()
            self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

            self._set_light_state()
            self._previous_state = self.state

    def _pre_off_configured(self) -> bool:
        """Check whether pre-off is configured for the current day/night/sleep state.

        Returns:
            True if pre-off is configured
        """
        return bool(self._timeout_pre_off)

    def _leaving_configured(self) -> bool:
        """Check whether leaving is configured for the current day/night/sleep state.

        Returns:
            True if leaving is configured
        """
        if self._config.parameter.leaving_only_if_on and self._config.items.light.is_off():
            return False

        return bool(self._timeout_leaving)

    def _pre_sleep_configured(self) -> bool:
        """Check whether pre-sleep is configured for the current day/night state.

        Returns:
            True if pre-sleep is configured
        """
        if self._config.items.sleeping_state is None:
            return False

        pre_sleep_prevent = False
        if self._config.items.pre_sleep_prevent is not None:
            pre_sleep_prevent = self._config.items.pre_sleep_prevent.is_on()
        elif self._config.parameter.pre_sleep_prevent is not None:
            try:
                pre_sleep_prevent = self._config.parameter.pre_sleep_prevent()
            except Exception:
                self._instance_logger.exception("Could not execute pre_sleep_prevent function. pre_sleep_prevent will be set to False.")
                pre_sleep_prevent = False

        return bool(self._timeout_pre_sleep) and not pre_sleep_prevent

    def on_enter_auto_restoreState(self) -> None:  # noqa: N802
        """On enter of state auto_restoreState."""
        self._restore_state = "auto_off" if self._restore_state == "auto_preoff" else self._restore_state

        if self._restore_state:
            self._set_state(self._restore_state)

    def _was_on_before(self) -> bool:
        """Check whether the dimmer was on before.

        Returns:
            True if the dimmer was on before, else False
        """
        return bool(self._brightness_before)

    def _set_timeouts(self) -> None:
        """Set timeouts depending on the current day/night/sleep state."""
        if self._get_sleeping_activ():
            self._timeout_on = self._config.parameter.on.sleeping.timeout
            self._timeout_pre_off = getattr(self._config.parameter.pre_off.sleeping if self._config.parameter.pre_off else 0, "timeout", 0)
            self._timeout_leaving = getattr(self._config.parameter.leaving.sleeping if self._config.parameter.leaving else 0, "timeout", 0)
            self._timeout_pre_sleep = 0

        elif self._config.items.day.is_on():
            self._timeout_on = self._config.parameter.on.day.timeout
            self._timeout_pre_off = getattr(self._config.parameter.pre_off.day if self._config.parameter.pre_off else 0, "timeout", 0)
            self._timeout_leaving = getattr(self._config.parameter.leaving.day if self._config.parameter.leaving else 0, "timeout", 0)
            self._timeout_pre_sleep = getattr(self._config.parameter.pre_sleep.day if self._config.parameter.pre_sleep else 0, "timeout", 0)
        else:
            self._timeout_on = self._config.parameter.on.night.timeout
            self._timeout_pre_off = getattr(self._config.parameter.pre_off.night if self._config.parameter.pre_off else 0, "timeout", 0)
            self._timeout_leaving = getattr(self._config.parameter.leaving.night if self._config.parameter.leaving else 0, "timeout", 0)
            self._timeout_pre_sleep = getattr(self._config.parameter.pre_sleep.night if self._config.parameter.pre_sleep else 0, "timeout", 0)

        self.state_machine.states["auto"].states["on"].timeout = self._timeout_on
        self.state_machine.states["auto"].states["preoff"].timeout = self._timeout_pre_off
        self.state_machine.states["auto"].states["leaving"].timeout = self._timeout_leaving
        self.state_machine.states["auto"].states["presleep"].timeout = self._timeout_pre_sleep

    @abc.abstractmethod
    def _set_light_state(self) -> None:
        """Set brightness to light."""

    def _get_target_brightness(self) -> bool | float | None:  # noqa: C901, PLR0912
        """Get configured brightness for the current day/night/sleep state.

        Returns:
             brightness value
        """
        sleeping_active = self._get_sleeping_activ(include_pre_sleep=True)

        if self.state == "auto_on":
            if self._previous_state == "manual":
                return None
            if self._previous_state in {"auto_preoff", "auto_leaving", "auto_presleep"}:
                return self._brightness_before

            # starting from here: previous state == auto_off
            if isinstance(man_value := self._state_observer.last_manual_event.value, int | float) and 0 < man_value < 100:  # noqa: PLR2004
                return None
            if self._state_observer.last_manual_event.value == "INCREASE":
                return None

            if sleeping_active:
                brightness_from_config = self._config.parameter.on.sleeping.brightness
            elif self._config.items.day.is_on():
                brightness_from_config = self._config.parameter.on.day.brightness
            else:
                brightness_from_config = self._config.parameter.on.night.brightness

            if brightness_from_config is True and self._state_observer.last_manual_event.value == "ON":
                return None

            return brightness_from_config

        if self.state == "auto_preoff":
            self._brightness_before = self._state_observer.value

            if sleeping_active:
                brightness_from_config = getattr(self._config.parameter.pre_off.sleeping if self._config.parameter.pre_off else None, "brightness", None)
            elif self._config.items.day.is_on():
                brightness_from_config = getattr(self._config.parameter.pre_off.day if self._config.parameter.pre_off else None, "brightness", None)
            else:
                brightness_from_config = getattr(self._config.parameter.pre_off.night if self._config.parameter.pre_off else None, "brightness", None)

            if brightness_from_config is None:
                return None

            if isinstance(self._state_observer.value, float | int) and brightness_from_config > self._state_observer.value:
                return math.ceil(self._state_observer.value / 2)
            return brightness_from_config

        if self.state == "auto_off":
            if self._previous_state == "manual":
                return None
            return False

        if self.state == "auto_presleep":
            if self._config.items.day.is_on():
                return getattr(self._config.parameter.pre_sleep.day if self._config.parameter.pre_sleep else None, "brightness", None)
            return getattr(self._config.parameter.pre_sleep.night if self._config.parameter.pre_sleep else None, "brightness", None)

        if self.state == "auto_leaving":
            if sleeping_active:
                return getattr(self._config.parameter.leaving.sleeping if self._config.parameter.leaving else None, "brightness", None)
            if self._config.items.day.is_on():
                return getattr(self._config.parameter.leaving.day if self._config.parameter.leaving else None, "brightness", None)
            return getattr(self._config.parameter.leaving.night if self._config.parameter.leaving else None, "brightness", None)

        return None

    def on_enter_auto_init(self) -> None:
        """Callback, which is called on enter of init state."""
        if self._config.items.light.is_on():
            self.to_auto_on()
        else:
            self.to_auto_off()

    def _get_sleeping_activ(self, include_pre_sleep: bool = False) -> bool:
        """Get if sleeping is active.

        Args:
            include_pre_sleep: if true, also pre sleep will be handled as sleeping

        Returns:
            true if sleeping active
        """
        sleep_states = [habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value] if include_pre_sleep else [habapp_rules.system.SleepState.SLEEPING.value]
        return getattr(self._config.items.sleeping_state, "value", "") in sleep_states

    def _cb_hand_on(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:  # noqa: ARG002
        """Callback, which is triggered by the state observer if a manual ON command was detected.

        Args:
            event: original trigger event
        """
        self._instance_logger.debug("Hand 'ON' detected")
        self.hand_on()

    def _cb_hand_off(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:  # noqa: ARG002
        """Callback, which is triggered by the state observer if a manual OFF command was detected.

        Args:
            event: original trigger event
        """
        self._instance_logger.debug("Hand 'OFF' detected")
        self.hand_off()

    def _cb_manu(self, event: HABApp.openhab.events.ItemStateUpdatedEvent) -> None:
        """Callback, which is triggered if the manual switch has a state event.

        Args:
            event: trigger event
        """
        if event.value == "ON":
            self.manual_on()
        else:
            self.manual_off()

    def _cb_day(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa: ARG002
        """Callback, which is triggered if the day/night switch has a state change event.

        Args:
            event: trigger event
        """
        self._set_timeouts()

    def _cb_presence(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the presence state has a state change event.

        Args:
            event: trigger event
        """
        self._set_timeouts()
        if event.value == habapp_rules.system.PresenceState.LEAVING.value:
            self._brightness_before = self._state_observer.value
            self._restore_state = self._previous_state
            self.leaving_started()
        elif event.value == habapp_rules.system.PresenceState.PRESENCE.value and self.state == "auto_leaving":
            self.leaving_aborted()

    def _cb_sleeping(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the sleep state has a state change event.

        Args:
            event: trigger event
        """
        self._set_timeouts()
        if event.value == habapp_rules.system.SleepState.PRE_SLEEPING.value:
            self._brightness_before = self._state_observer.value
            self._restore_state = self._previous_state
            self.__time_sleep_start = time.time()
            self.sleep_started()
        elif event.value == habapp_rules.system.SleepState.AWAKE.value and time.time() - self.__time_sleep_start <= MINUTE_IN_SEC:
            self.sleep_aborted()


class LightSwitch(_LightBase):
    """Rules class to manage basic light states.

    # KNX-things:
    Thing device T00_99_OpenHab_DimmerObserver "KNX OpenHAB dimmer observer"{
            Type switch             : light             "Light"             [ switch="1/1/10+1/1/13" ]
    }

    # Items:
    Switch    I01_01_Light              "Light"             {channel="knx:device:bridge:T00_99_OpenHab_DimmerObserver:light"}
    Switch    I00_00_Light_manual       "Light manual"

    # Config:
    config = habapp_rules.actors.config.light.LightConfig(
            items = habapp_rules.actors.config.light.LightItems(
                    light="I01_01_Light",
                    manual="I00_00_Light_manual",
                    presence_state="I999_00_Presence_state",
                    sleeping_state="I999_00_Sleeping_state",
                    day="I999_00_Day"
            )
    )

    # Rule init:
    habapp_rules.actors.light.LightSwitch(config)
    """

    def __init__(self, config: habapp_rules.actors.config.light.LightConfig) -> None:
        """Init of basic light object.

        Args:
            config: light config

        Raises:
            TypeError: if type of light_item is not supported
        """
        if not isinstance(config.items.light, HABApp.openhab.items.switch_item.SwitchItem):
            msg = f"type: {type(config.items.light)} is not supported!"
            raise TypeError(msg)

        self._state_observer = habapp_rules.actors.state_observer.StateObserverSwitch(config.items.light.name, self._cb_hand_on, self._cb_hand_off)

        _LightBase.__init__(self, config)

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item and other states."""
        _LightBase._update_openhab_state(self)  # noqa: SLF001

        if self.state == "auto_preoff":
            timeout = self.state_machine.get_state(self.state).timeout

            warn_thread_1 = threading.Thread(target=self.__trigger_warning, args=("auto_preoff", 0, 1), daemon=True)
            warn_thread_1.start()

            if timeout > MINUTE_IN_SEC:
                # add additional warning for long timeouts
                warn_thread_2 = threading.Thread(target=self.__trigger_warning, args=("auto_preoff", timeout / 2, 2), daemon=True)
                warn_thread_2.start()

    def __trigger_warning(self, state_name: str, wait_time: float, switch_off_amount: int) -> None:
        """Trigger light switch off warning.

        Args:
            state_name: name of state where the warning should be triggered. If different no command will be sent
            wait_time: time between start of the thread and switch off / on
            switch_off_amount: number of switch off
        """
        if wait_time:
            time.sleep(wait_time)

        for idx in range(switch_off_amount):
            if self.state != state_name:
                break
            self._state_observer.send_command("OFF")
            time.sleep(0.2)
            if self.state != state_name:
                break
            self._state_observer.send_command("ON")
            if idx + 1 < switch_off_amount:
                time.sleep(0.5)

    def _set_light_state(self) -> None:
        """Set brightness to light."""
        target_value = self._get_target_brightness()
        if target_value is None or self._previous_state is None:
            # don't change value if target_value is None or _set_light_state will be called during init (_previous_state == None)
            return

        target_value = "ON" if target_value else "OFF"
        self._instance_logger.debug(f"set brightness {target_value}")
        self._state_observer.send_command(target_value)


class LightDimmer(_LightBase):
    """Rules class to manage basic light states.

    # KNX-things:
    Thing device T00_99_OpenHab_DimmerObserver "KNX OpenHAB dimmer observer"{
            Type dimmer             : light             "Light"             [ switch="1/1/10", position="1/1/13+<1/1/15" ]
            Type dimmer-control     : light_ctr         "Light control"     [ increaseDecrease="1/1/12"]
            Type dimmer             : light_group       "Light Group"       [ switch="1/1/240", position="1/1/243"]
    }

    # Items:
    Dimmer    I01_01_Light              "Light"             {channel="knx:device:bridge:T00_99_OpenHab_DimmerObserver:light"}
    Dimmer    I01_01_Light_ctr          "Light ctr"         {channel="knx:device:bridge:T00_99_OpenHab_DimmerObserver:light_ctr"}
    Dimmer    I01_01_Light_group        "Light Group"       {channel="knx:device:bridge:T00_99_OpenHab_DimmerObserver:light_group"}
    Switch    I00_00_Light_manual       "Light manual"

    # Config:
    config = habapp_rules.actors.config.light.LightConfig(
            items=habapp_rules.actors.config.light.LightItems(
                    light="I01_01_Light",
                    light_control=["I01_01_Light_ctr"],
                    manual="I00_00_Light_manual",
                    presence_state="I999_00_Presence_state",
                    sleeping_state="I999_00_Sleeping_state",
                    day="I999_00_Day"
            )
    )

    # Rule init:
    habapp_rules.actors.light.LightDimmer(config)
    """

    trans = copy.deepcopy(_LightBase.trans)
    trans.append({"trigger": "hand_changed", "source": "auto_on", "dest": "auto_on"})

    def __init__(self, config: habapp_rules.actors.config.light.LightConfig) -> None:
        """Init of basic light object.

        Args:
            config: light config

        Raises:
            TypeError: if type of light_item is not supported
        """
        if not isinstance(config.items.light, HABApp.openhab.items.dimmer_item.DimmerItem):
            msg = f"type: {type(config.items.light)} is not supported!"
            raise TypeError(msg)

        control_names = [item.name for item in config.items.light_control]
        group_names = [item.name for item in config.items.light_groups]
        self._state_observer = habapp_rules.actors.state_observer.StateObserverDimmer(config.items.light.name, self._cb_hand_on, self._cb_hand_off, self._cb_hand_changed, control_names=control_names, group_names=group_names)

        _LightBase.__init__(self, config)

    def _set_light_state(self) -> None:
        """Set brightness to light."""
        target_value = self._get_target_brightness()
        if target_value is None or self._previous_state is None:
            # don't change value if target_value is None or _set_light_state will be called during init (_previous_state == None)
            return

        if isinstance(target_value, bool):
            target_value = "ON" if target_value else "OFF"
        self._instance_logger.debug(f"set brightness {target_value}")
        self._state_observer.send_command(target_value)

    def _cb_hand_changed(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent | HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered by the state observer if a manual OFF command was detected.

        Args:
            event: original trigger event
        """
        if isinstance(event, HABApp.openhab.events.ItemStateChangedEvent) and abs(event.value - event.old_value) > DIMMER_VALUE_TOLERANCE:
            self.hand_changed()


class _LightExtendedMixin:
    """Mixin class for adding door and motion functionality."""

    states: dict
    trans: list
    state: str
    _config: habapp_rules.actors.config.light.LightConfig
    state_machine: habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout
    _get_sleeping_activ: Callable[[bool | None], bool]

    def __init__(self, config: habapp_rules.actors.config.light.LightConfig) -> None:
        """Init mixin class.

        Args:
            config: light config
        """
        self.states = _LightExtendedMixin._add_additional_states(self.states)
        self.trans = _LightExtendedMixin._add_additional_transitions(self.trans)

        self._timeout_motion = 0
        self._timeout_door = 0

        self._hand_off_lock_time = config.parameter.hand_off_lock_time
        self._hand_off_timestamp = 0

    @staticmethod
    def _add_additional_states(states_dict: dict) -> dict:
        """Add additional states for door and motion.

        Args:
            states_dict: current state dictionary

        Returns:
            current + new states
        """
        states_dict = copy.deepcopy(states_dict)
        states_dict[1]["children"].append({"name": "door", "timeout": 999, "on_timeout": "door_timeout"})
        states_dict[1]["children"].append({"name": "motion", "timeout": 999, "on_timeout": "motion_timeout"})
        return states_dict

    @staticmethod
    def _add_additional_transitions(transitions_list: list[dict]) -> list[dict]:
        """Add additional transitions for door and motion.

        Args:
            transitions_list: current transitions

        Returns:
            current + new transitions
        """
        transitions_list = copy.deepcopy(transitions_list)

        transitions_list.append({"trigger": "motion_on", "source": "auto_door", "dest": "auto_motion", "conditions": "_motion_configured"})
        transitions_list.append({"trigger": "motion_on", "source": "auto_off", "dest": "auto_motion", "conditions": ["_motion_configured", "_motion_door_allowed"]})
        transitions_list.append({"trigger": "motion_on", "source": "auto_preoff", "dest": "auto_motion", "conditions": "_motion_configured"})
        transitions_list.append({"trigger": "motion_off", "source": "auto_motion", "dest": "auto_preoff", "conditions": "_pre_off_configured"})
        transitions_list.append({"trigger": "motion_off", "source": "auto_motion", "dest": "auto_off", "unless": "_pre_off_configured"})
        transitions_list.append({"trigger": "motion_timeout", "source": "auto_motion", "dest": "auto_preoff", "conditions": "_pre_off_configured", "before": "_log_motion_timeout_warning"})
        transitions_list.append({"trigger": "motion_timeout", "source": "auto_motion", "dest": "auto_off", "unless": "_pre_off_configured", "before": "_log_motion_timeout_warning"})
        transitions_list.append({"trigger": "hand_off", "source": "auto_motion", "dest": "auto_off"})

        transitions_list.append({"trigger": "door_opened", "source": ["auto_off", "auto_preoff", "auto_door"], "dest": "auto_door", "conditions": ["_door_configured", "_motion_door_allowed"]})
        transitions_list.append({"trigger": "door_timeout", "source": "auto_door", "dest": "auto_preoff", "conditions": "_pre_off_configured"})
        transitions_list.append({"trigger": "door_timeout", "source": "auto_door", "dest": "auto_off", "unless": "_pre_off_configured"})
        transitions_list.append({"trigger": "door_closed", "source": "auto_leaving", "dest": "auto_off", "conditions": "_door_off_leaving_configured"})
        transitions_list.append({"trigger": "hand_off", "source": "auto_door", "dest": "auto_off"})

        transitions_list.append({"trigger": "leaving_started", "source": ["auto_motion", "auto_door"], "dest": "auto_leaving", "conditions": "_leaving_configured"})
        transitions_list.append({"trigger": "sleep_started", "source": ["auto_motion", "auto_door"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"})

        return transitions_list

    def add_additional_callbacks(self) -> None:
        """Add additional callbacks for motion and door items."""
        if self._config.items.motion is not None:
            self._config.items.motion.listen_event(self._cb_motion, HABApp.openhab.events.ItemStateChangedEventFilter())
        for item_door in self._config.items.doors:
            item_door.listen_event(self._cb_door, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _get_initial_state(self, default_value: str = "") -> str:
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        initial_state = _LightBase._get_initial_state(self, default_value)  # noqa: SLF001

        if initial_state == "auto_on" and self._config.items.motion is not None and self._config.items.motion.is_on() and self._motion_configured():
            initial_state = "auto_motion"
        return initial_state

    def _set_timeouts(self) -> None:
        """Set timeouts depending on the current day/night/sleep state."""
        _LightBase._set_timeouts(self)  # noqa: SLF001

        # set timeouts of additional states
        if self._get_sleeping_activ():
            self._timeout_motion = getattr(self._config.parameter.motion.sleeping if self._config.parameter.motion else 0, "timeout", 0)
            self._timeout_door = getattr(self._config.parameter.door.sleeping if self._config.parameter.door else 0, "timeout", 0)

        elif self._config.items.day.is_on():
            self._timeout_motion = getattr(self._config.parameter.motion.day if self._config.parameter.motion else 0, "timeout", 0)
            self._timeout_door = getattr(self._config.parameter.door.day if self._config.parameter.door else 0, "timeout", 0)
        else:
            self._timeout_motion = getattr(self._config.parameter.motion.night if self._config.parameter.motion else 0, "timeout", 0)
            self._timeout_door = getattr(self._config.parameter.door.night if self._config.parameter.door else 0, "timeout", 0)

        self.state_machine.states["auto"].states["motion"].timeout = self._timeout_motion
        self.state_machine.states["auto"].states["door"].timeout = self._timeout_door

    def _get_target_brightness(self) -> bool | float | None:
        """Get configured brightness for the current day/night/sleep state. Must be called before _get_target_brightness of base class.

        Returns:
            configured brightness value

        Raises:
            habapp_rules.core.exceptions.HabAppRulesError: if current state is not supported
        """
        if self.state == "auto_motion":
            if self._get_sleeping_activ(include_pre_sleep=True):
                return getattr(self._config.parameter.motion.sleeping if self._config.parameter.motion else None, "brightness", None)
            if self._config.items.day.is_on():
                return getattr(self._config.parameter.motion.day if self._config.parameter.motion else None, "brightness", None)
            return getattr(self._config.parameter.motion.night if self._config.parameter.motion else None, "brightness", None)

        if self.state == "auto_door":
            if self._get_sleeping_activ(include_pre_sleep=True):
                return getattr(self._config.parameter.door.sleeping if self._config.parameter.door else None, "brightness", None)
            if self._config.items.day.is_on():
                return getattr(self._config.parameter.door.day if self._config.parameter.door else None, "brightness", None)
            return getattr(self._config.parameter.door.night if self._config.parameter.door else None, "brightness", None)

        return _LightBase._get_target_brightness(self)  # noqa: SLF001

    def _door_configured(self) -> bool:
        """Check whether door functionality is configured for the current day/night state.

        Returns:
            True if door functionality is configured
        """
        if not self._config.items.doors:
            return False
        return bool(self._timeout_door)

    def _door_off_leaving_configured(self) -> bool:
        """Check whether door-off functionality is configured for the current day/night state.

        Returns:
            True if door-off is configured
        """
        return self._config.parameter.off_at_door_closed_during_leaving

    def _motion_configured(self) -> bool:
        """Check whether motion functionality is configured for the current day/night state.

        Returns:
            True if motion functionality is configured
        """
        if self._config.items.motion is None:
            return False
        return bool(self._timeout_motion)

    def _motion_door_allowed(self) -> bool:
        """Check if transition to motion and door state is allowed.

        Returns:
            True if transition is allowed
        """
        return time.time() - self._hand_off_timestamp > self._hand_off_lock_time

    def _cb_hand_off(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
        """Callback, which is triggered by the state observer if a manual OFF command was detected.

        Args:
            event: original trigger event
        """
        self._hand_off_timestamp = time.time()
        _LightBase._cb_hand_off(self, event)  # noqa: SLF001

    def _cb_motion(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the motion state changed.

        Args:
            event: trigger event
        """
        if event.value == "ON":
            self.motion_on()
        else:
            self.motion_off()

    def _cb_door(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if a door state changed.

        Args:
            event: trigger event
        """
        if event.value == "OPEN":
            # every open of a single door calls door_opened()
            self.door_opened()

        if event.value == "CLOSED" and all(door.is_closed() for door in self._config.items.doors):
            # only if all doors are closed door_closed() is called
            self.door_closed()

    def _log_motion_timeout_warning(self) -> None:
        """Log warning if motion state was left because of timeout."""
        self._instance_logger.warning("Timeout of motion was triggered, before motion stopped. Thing about to increase motion timeout!")


class LightSwitchExtended(_LightExtendedMixin, LightSwitch):
    """Extended Light.

    Example config is given at Light base class.
    With this class additionally motion or door items can be given.
    """

    def __init__(self, config: habapp_rules.actors.config.light.LightConfig) -> None:
        """Init of extended light object.

        Args:
            config: light config
        """
        _LightExtendedMixin.__init__(self, config)
        LightSwitch.__init__(self, config)

        _LightExtendedMixin.add_additional_callbacks(self)


class LightDimmerExtended(_LightExtendedMixin, LightDimmer):
    """Extended Light.

    Example config is given at Light base class.
    With this class additionally motion or door items can be given.
    """

    def __init__(self, config: habapp_rules.actors.config.light.LightConfig) -> None:
        """Init of extended light object.

        Args:
            config: light config
        """
        _LightExtendedMixin.__init__(self, config)
        LightDimmer.__init__(self, config)

        _LightExtendedMixin.add_additional_callbacks(self)
