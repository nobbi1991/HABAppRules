"""Rules to manage shading objects."""

import abc
import datetime
import logging
import time
import typing

import HABApp

import habapp_rules.actors.config.shading
import habapp_rules.actors.state_observer
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system

LOGGER = logging.getLogger(__name__)

HAND_IGNORE_TIME = 1.5


class _ShadingBase(habapp_rules.core.state_machine_rule.StateMachineRule):
    """Base class for shading objects."""

    states: typing.ClassVar = [
        {"name": "WindAlarm"},
        {"name": "Manual"},
        {"name": "Hand", "timeout": 20 * 3600, "on_timeout": "_auto_hand_timeout"},
        {
            "name": "Auto",
            "initial": "Init",
            "children": [
                {"name": "Init"},
                {"name": "Open"},
                {"name": "DoorOpen", "initial": "Open", "children": [{"name": "Open"}, {"name": "PostOpen", "timeout": 5 * 60, "on_timeout": "_timeout_post_door_open"}]},
                {"name": "NightClose"},
                {"name": "SleepingClose"},
                {"name": "SunProtection"},
            ],
        },
    ]

    trans: typing.ClassVar = [
        # wind alarm
        {"trigger": "_wind_alarm_on", "source": ["Auto", "Hand", "Manual"], "dest": "WindAlarm"},
        {"trigger": "_wind_alarm_off", "source": "WindAlarm", "dest": "Manual", "conditions": "_manual_active"},
        {"trigger": "_wind_alarm_off", "source": "WindAlarm", "dest": "Auto", "unless": "_manual_active"},
        # manual
        {"trigger": "_manual_on", "source": ["Auto", "Hand"], "dest": "Manual"},
        {"trigger": "_manual_off", "source": "Manual", "dest": "Auto"},
        # hand
        {"trigger": "_hand_command", "source": ["Auto"], "dest": "Hand"},
        {"trigger": "_auto_hand_timeout", "source": "Hand", "dest": "Auto"},
        # sun
        {"trigger": "_sun_on", "source": "Auto_Open", "dest": "Auto_SunProtection"},
        {"trigger": "_sun_off", "source": "Auto_SunProtection", "dest": "Auto_Open"},
        # sleep
        {"trigger": "_sleep_started", "source": ["Auto_Open", "Auto_NightClose", "Auto_SunProtection", "Auto_DoorOpen"], "dest": "Auto_SleepingClose"},
        {"trigger": "_sleep_started", "source": "Hand", "dest": "Auto"},
        {"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_SunProtection", "conditions": "_sun_protection_active_and_configured"},
        {"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_NightClose", "conditions": ["_night_active_and_configured"]},
        {"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_Open", "unless": ["_night_active_and_configured", "_sun_protection_active_and_configured"]},
        # door
        {"trigger": "_door_open", "source": ["Auto_NightClose", "Auto_SunProtection", "Auto_SleepingClose", "Auto_Open"], "dest": "Auto_DoorOpen"},
        {"trigger": "_door_open", "source": "Auto_DoorOpen_PostOpen", "dest": "Auto_DoorOpen_Open"},
        {"trigger": "_door_closed", "source": "Auto_DoorOpen_Open", "dest": "Auto_DoorOpen_PostOpen"},
        {"trigger": "_timeout_post_door_open", "source": "Auto_DoorOpen_PostOpen", "dest": "Auto_Init"},
        # night close
        {"trigger": "_night_started", "source": ["Auto_Open", "Auto_SunProtection"], "dest": "Auto_NightClose", "conditions": "_night_active_and_configured"},
        {"trigger": "_night_stopped", "source": "Auto_NightClose", "dest": "Auto_SunProtection", "conditions": "_sun_protection_active_and_configured"},
        {"trigger": "_night_stopped", "source": "Auto_NightClose", "dest": "Auto_Open", "unless": ["_sun_protection_active_and_configured"]},
    ]
    _state_observer_pos: habapp_rules.actors.state_observer.StateObserverRollerShutter | habapp_rules.actors.state_observer.StateObserverDimmer

    def __init__(self, config: habapp_rules.actors.config.shading.ShadingConfig) -> None:
        """Init of _ShadingBase.

        Args:
            config: shading config

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationException: if given config / items are not valid
        """
        self._config = config
        self._set_shading_state_timestamp = 0

        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.shading_position.name)

        # init state machine
        self._previous_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_initial_state()
        self._apply_config()

        self._position_before = habapp_rules.actors.config.shading.ShadingPosition(self._config.items.shading_position.value)

        if isinstance(self._config.items.shading_position, HABApp.openhab.items.rollershutter_item.RollershutterItem):
            self._state_observer_pos = habapp_rules.actors.state_observer.StateObserverRollerShutter(
                self._config.items.shading_position.name, self._cb_hand, [item.name for item in self._config.items.shading_position_control], [item.name for item in self._config.items.shading_position_group], self._config.parameter.value_tolerance
            )
        else:
            # self._config.items.shading_position is instance of HABApp.openhab.items.dimmer_item.DimmerItem
            self._state_observer_pos = habapp_rules.actors.state_observer.StateObserverDimmer(
                self._config.items.shading_position.name,
                self._cb_hand,
                self._cb_hand,
                self._cb_hand,
                [item.name for item in self._config.items.shading_position_control],
                [item.name for item in self._config.items.shading_position_group],
                self._config.parameter.value_tolerance,
            )

        # callbacks
        self._config.items.manual.listen_event(self._cb_manual, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.wind_alarm is not None:
            self._config.items.wind_alarm.listen_event(self._cb_wind_alarm, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.sun_protection is not None:
            self._config.items.sun_protection.listen_event(self._cb_sun, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.sleeping_state is not None:
            self._config.items.sleeping_state.listen_event(self._cb_sleep_state, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.night is not None:
            self._config.items.night.listen_event(self._cb_night, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.door is not None:
            self._config.items.door.listen_event(self._cb_door, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._update_openhab_state()

    def _apply_config(self) -> None:
        """Apply config to state machine."""
        # set timeouts
        self.state_machine.states["Auto"].states["DoorOpen"].states["PostOpen"].timeout = self._config.parameter.door_post_time
        self.state_machine.states["Manual"].timeout = self._config.parameter.manual_timeout

    def _get_initial_state(self, default_value: str = "") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        if self._config.items.wind_alarm is not None and self._config.items.wind_alarm.is_on():
            return "WindAlarm"
        if self._config.items.manual.is_on():
            return "Manual"
        if self._config.items.door is not None and self._config.items.door.is_open():  # self._item_door.is_open():
            return "Auto_DoorOpen_Open"
        if self._config.items.sleeping_state is not None and self._config.items.sleeping_state.value in {habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value}:
            return "Auto_SleepingClose"
        if self._config.items.night is not None and self._config.items.night.is_on() and self._night_active_and_configured():
            return "Auto_NightClose"
        if self._sun_protection_active_and_configured():
            return "Auto_SunProtection"
        return "Auto_Open"

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item and other states.

        This method should be set to "after_state_change" of the state machine.
        """
        if self.state != self._previous_state:
            super()._update_openhab_state()
            self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

            self._set_shading_state()

            if self._config.items.hand_manual_is_active_feedback is not None:
                self._config.items.hand_manual_is_active_feedback.oh_post_update("ON" if self.state in {"Manual", "Hand"} else "OFF")

            self._previous_state = self.state

    def _set_shading_state(self) -> None:
        """Set shading state."""
        if self._previous_state is None:
            # don't change value if called during init (_previous_state == None)
            return

        self._set_shading_state_timestamp = time.time()
        self._apply_target_position(self._get_target_position())

    @abc.abstractmethod
    def _apply_target_position(self, target_position: habapp_rules.actors.config.shading.ShadingPosition) -> None:
        """Apply target position by sending it via the observer(s).

        Args:
            target_position: target position of the shading object
        """

    def _get_target_position(self) -> habapp_rules.actors.config.shading.ShadingPosition | None:  # noqa: C901
        """Get target position for shading object.

        Returns:
            target shading position
        """
        if self.state in {"Hand", "Manual"}:
            if self._previous_state == "WindAlarm":
                return self._position_before
            return None

        if self.state == "WindAlarm":
            return self._config.parameter.pos_wind_alarm

        if self.state == "Auto_Open":
            return self._config.parameter.pos_auto_open

        if self.state == "Auto_SunProtection":
            return self._config.parameter.pos_sun_protection

        if self.state == "Auto_SleepingClose":
            if self._config.items.night is None:
                return self._config.parameter.pos_sleeping_night
            return self._config.parameter.pos_sleeping_night if self._config.items.night.is_on() else self._config.parameter.pos_sleeping_day

        if self.state == "Auto_NightClose":
            if self._config.items.summer is not None and self._config.items.summer.is_on():
                return self._config.parameter.pos_night_close_summer
            return self._config.parameter.pos_night_close_winter

        if self.state == "Auto_DoorOpen_Open":
            return self._config.parameter.pos_door_open

        return None

    def on_enter_Auto_Init(self) -> None:  # noqa: N802
        """Is called on entering of init state."""
        self._set_initial_state()

    def on_exit_Manual(self) -> None:  # noqa: N802
        """Is called if state Manual is left."""
        self._set_position_before()

    def on_exit_Hand(self) -> None:  # noqa: N802
        """Is called if state Hand is left."""
        self._set_position_before()

    def _set_position_before(self) -> None:
        """Set / save position before manual state is entered. This is used to restore the previous position."""
        self._position_before = habapp_rules.actors.config.shading.ShadingPosition(self._config.items.shading_position.value)

    def _manual_active(self) -> bool:
        """Check if manual is active.

        Returns:
            True if night is active
        """
        return self._config.items.manual.is_on()

    def _sun_protection_active_and_configured(self) -> bool:
        """Check if sun protection is active.

        Returns:
            True if night is active
        """
        return self._config.items.sun_protection is not None and self._config.items.sun_protection.is_on() and self._config.parameter.pos_sun_protection is not None

    def _night_active_and_configured(self) -> bool:
        """Check if night is active and configured.

        Returns:
            True if night is active
        """
        night_config = self._config.parameter.pos_night_close_summer if self._config.items.summer is not None and self._config.items.summer.is_on() else self._config.parameter.pos_night_close_winter
        return self._config.items.night is not None and self._config.items.night.is_on() and night_config is not None

    def _cb_hand(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if a external control was detected.

        Args:
            event: original trigger event
        """
        if time.time() - self._set_shading_state_timestamp > HAND_IGNORE_TIME:
            # ignore hand commands one second after this rule triggered a position change
            self._instance_logger.debug(f"Detected hand command. The event was {event}")
            self._hand_command()
        else:
            self._instance_logger.debug(f"Detected hand command, ignoring it. The event was {event}")

    def _cb_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if manual mode changed.

        Args:
            event: original trigger event
        """
        if event.value == "ON":
            self._manual_on()
        else:
            self._manual_off()

    def _cb_wind_alarm(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if wind alarm changed.

        Args:
            event: original trigger event
        """
        if event.value == "ON":
            self._wind_alarm_on()
        else:
            self._wind_alarm_off()

    def _cb_sun(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if sun state changed.

        Args:
            event: original trigger event
        """
        if event.value == "ON":
            self._sun_on()
        else:
            self._sun_off()

    def _cb_sleep_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if sleeping state changed.

        Args:
            event: original trigger event
        """
        if event.value == habapp_rules.system.SleepState.PRE_SLEEPING.value:
            self._sleep_started()
        elif event.value == habapp_rules.system.SleepState.POST_SLEEPING.value:
            self._sleep_stopped()

    def _cb_night(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if night / dark state changed.

        Args:
            event: original trigger event
        """
        if self.state == "Auto_SleepingClose":
            target_position = self._config.parameter.pos_sleeping_night if event.value == "ON" else self._config.parameter.pos_sleeping_day
            self._apply_target_position(target_position)

        if event.value == "ON":
            self._night_started()
        else:
            self._night_stopped()

    def _cb_door(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if door state changed.

        Args:
            event: original trigger event
        """
        if event.value == "OPEN":
            self._door_open()
        else:
            self._door_closed()


class Shutter(_ShadingBase):
    """Rules class to manage a normal shutters (or curtains).

    # KNX-things:
    Thing device KNX_Shading "KNX OpenHAB dimmer observer"{
        Type dimmer                 : shading_position          "Shading position"          [ position="5.001:4/1/12+<4/1/15" ]
        Type dimmer-control         : shading_position_ctr      "Shading position ctr"      [ position="5.001:4/1/12+<4/1/15" ]
        Type dimmer-control         : shading_group_all_ctr     "Shading all ctr"           [ position="5.001:4/1/112+<4/1/115""]
        Type switch-control         : shading_hand_manual_ctr   "Shading hand / manual"     [ ga="4/1/20" ]
    }

    # Items:
    Rollershutter    shading_position       "Shading position"                  <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_position"}
    Rollershutter    shading_position_ctr   "Shading position ctr"              <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_position_ctr"}
    Dimmer           shading_slat           "Shading slat"                      <slat>              {channel="knx:device:bridge:KNX_Shading:shading_slat"}
    Switch           shading_manual         "Shading manual"
    Rollershutter    shading_all_ctr        "Shading all ctr"                   <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_group_all_ctr"}
    Switch           shading_hand_manual    "Shading in Hand / Manual state"                        {channel="knx:device:bridge:KNX_Shading:shading_hand_manual_ctr"}

    # Config:
    config = habapp_rules.actors.config.shading.ShadingConfig(
            items = habapp_rules.actors.config.shading.ShadingItems(
                    shading_position="shading_position",
                    shading_position_control=["shading_position_ctr", "shading_all_ctr"],
                    slat="shading_slat",
                    manual="shading_manual",
                    wind_alarm="I99_99_WindAlarm",
                    sun_protection="I99_99_SunProtection",
                    sleeping_state="I99_99_Sleeping_State",
                    night="I99_99_Night",
                    door="I99_99_Door",
                    summer="I99_99_Summer",
                    hand_manual_is_active_feedback="shading_hand_manual"
            )
    )

    # Rule init:
    habapp_rules.actors.shading.Shutter(config)
    """

    def __init__(self, config: habapp_rules.actors.config.shading.ShadingConfig) -> None:
        """Init of Raffstore object.

        Args:
            config: shading config
        """
        _ShadingBase.__init__(self, config)

        self._instance_logger.debug(self.get_initial_log_message())

    def _apply_target_position(self, target_position: habapp_rules.actors.config.shading.ShadingPosition) -> None:
        """Apply target position by sending it via the observer(s).

        Args:
            target_position: target position of the shading object
        """
        if target_position is None:
            return

        if (position := target_position.position) is not None:
            self._state_observer_pos.send_command(position)
            self._instance_logger.debug(f"set position {target_position.position}")


class Raffstore(_ShadingBase):
    """Rules class to manage a raffstore.

    # KNX-things:
    Thing device KNX_Shading "KNX OpenHAB dimmer observer"{
        Type rollershutter          : shading_position          "Shading position"          [ upDown="4/1/10", stopMove="4/1/11", position="5.001:4/1/12+<4/1/15" ]
        Type rollershutter-control  : shading_position_ctr      "Shading position ctr"      [ upDown="4/1/10", stopMove="4/1/11" ]
        Type dimmer                 : shading_slat              "Shading slat"              [ position="5.001:4/1/13+<4/1/16" ]
        Type rollershutter-control  : shading_group_all_ctr     "Shading all ctr"           [ upDown="4/1/110", stopMove="4/1/111"]
        Type switch-control         : shading_hand_manual_ctr   "Shading hand / manual"     [ ga="4/1/20" ]
    }

    # Items:
    Rollershutter    shading_position       "Shading position"                  <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_position"}
    Rollershutter    shading_position_ctr   "Shading position ctr"              <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_position_ctr"}
    Dimmer           shading_slat           "Shading slat"                      <slat>              {channel="knx:device:bridge:KNX_Shading:shading_slat"}
    Switch           shading_manual         "Shading manual"
    Rollershutter    shading_all_ctr        "Shading all ctr"                   <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_group_all_ctr"}
    Switch           shading_hand_manual    "Shading in Hand / Manual state"                        {channel="knx:device:bridge:KNX_Shading:shading_hand_manual_ctr"}

    # Config:
    config = habapp_rules.actors.config.shading.ShadingConfig(
            items = habapp_rules.actors.config.shading.ShadingItems(
                    shading_position="shading_position",
                    shading_position_control=["shading_position_ctr", "shading_all_ctr"],
                    manual="shading_manual",
                    wind_alarm="I99_99_WindAlarm",
                    sun_protection="I99_99_SunProtection",
                    sleeping_state="I99_99_Sleeping_State",
                    night="I99_99_Night",
                    door="I99_99_Door",
                    summer="I99_99_Summer",
                    hand_manual_is_active_feedback="shading_hand_manual"
            )
    )

    # Rule init:
    habapp_rules.actors.shading.Raffstore(config)
    """

    def __init__(self, config: habapp_rules.actors.config.shading.ShadingConfig) -> None:
        """Init of Raffstore object.

        Args:
            config: shading config

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationError: if the correct items are given for sun protection mode
        """
        # check if the correct items are given for sun protection mode
        if (config.items.sun_protection is None) != (config.items.sun_protection_slat is None):
            msg = "Ether items.sun_protection AND items.sun_protection_slat item must be given or None of them."
            raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)
        if config.items.slat is None:
            msg = "Item for setting the slat value must be given."
            raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)

        _ShadingBase.__init__(self, config)

        self._state_observer_slat = habapp_rules.actors.state_observer.StateObserverSlat(config.items.slat.name, self._cb_hand, config.parameter.value_tolerance)

        # init items
        self.__verify_items()

        # callbacks
        if self._config.items.sun_protection_slat is not None:
            self._config.items.sun_protection_slat.listen_event(self._cb_slat_target, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._instance_logger.debug(self.get_initial_log_message())

    def __verify_items(self) -> None:
        """Check if given items are valid.

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationError: if given items are not valid
        """
        # check type of rollershutter item
        if not isinstance(self._config.items.shading_position, HABApp.openhab.items.rollershutter_item.RollershutterItem):
            msg = f"The shading position item must be of type RollershutterItem. Given: {type(self._config.items.shading_position)}"
            raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)

    def _get_target_position(self) -> habapp_rules.actors.config.shading.ShadingPosition | None:
        """Get target position for shading object(s).

        Returns:
            target shading position
        """
        target_position = super()._get_target_position()

        if self.state == "Auto_SunProtection" and target_position is not None:
            target_position.slat = self._config.items.sun_protection_slat.value

        return target_position

    def _apply_target_position(self, target_position: habapp_rules.actors.config.shading.ShadingPosition) -> None:
        """Apply target position by sending it via the observer(s).

        Args:
            target_position: target position of the shading object
        """
        if target_position is None:
            return

        if (position := target_position.position) is not None:
            self._state_observer_pos.send_command(position)

        if (slat := target_position.slat) is not None:
            self._state_observer_slat.send_command(slat)

        if any(pos is not None for pos in (position, slat)):
            self._instance_logger.debug(f"set position {target_position}")

    def _set_position_before(self) -> None:
        """Set / save position before manual state is entered. This is used to restore the previous position."""
        self._position_before = habapp_rules.actors.config.shading.ShadingPosition(self._config.items.shading_position.value, self._config.items.slat.value)

    def _cb_slat_target(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if the target slat value changed.

        Args:
            event: original trigger event
        """
        if self.state == "Auto_SunProtection":
            self._state_observer_slat.send_command(event.value)


class ResetAllManualHand(HABApp.Rule):
    """Clear the state hand / manual state of all shading.

    # Items:
    Switch           clear_hand_manual         "Clear Hand / Manual state of all shading objects"

    # Config
    config = habapp_rules.actors.config.shading.ResetAllManualHandConfig(
            items=habapp_rules.actors.config.shading.ResetAllManualHandItems(
                    reset_manual_hand="clear_hand_manual"
            )
    )

    # Rule init:
    habapp_rules.actors.shading.ResetAllManualHand(config)
    """

    def __init__(self, config: habapp_rules.actors.config.shading.ResetAllManualHandConfig) -> None:
        """Init of reset class.

        Args:
            config: config for reset all manual / hand rule
        """
        self._config = config
        HABApp.Rule.__init__(self)

        self._config.items.reset_manual_hand.listen_event(self._cb_reset_all, HABApp.openhab.events.ItemStateUpdatedEventFilter())

    def __get_shading_objects(self) -> list[_ShadingBase]:
        """Get all shading objects.

        Returns:
            list of shading objects
        """
        if self._config.parameter.shading_objects:
            return self._config.parameter.shading_objects
        return [rule for rule in self.get_rule(None) if issubclass(rule.__class__, _ShadingBase)]

    def _cb_reset_all(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
        """Callback which is called if reset is requested.

        Args:
            event: trigger event
        """
        if event.value == "OFF":
            return

        for shading_object in self.__get_shading_objects():
            state = shading_object.state
            manual_item = shading_object._config.items.manual  # noqa: SLF001

            if state == "Manual":
                manual_item.oh_send_command("OFF")

            elif state == "Hand":
                manual_item.oh_send_command("ON")
                manual_item.oh_send_command("OFF")

        self._config.items.reset_manual_hand.oh_send_command("OFF")


class SlatValueSun(HABApp.Rule):
    """Rules class to get slat value depending on sun elevation.

    # Items:
    Number    elevation             "Sun elevation"         <sun>     {channel="astro...}
    Number    sun_protection_slat   "Slat value"            <slat>

    # Config
    config = habapp_rules.actors.config.shading.SlatValueConfig(
            items=habapp_rules.actors.config.shading.SlatValueItems(
                    sun_elevation="elevation",
                    slat_value="sun_protection_slat",
                    summer="I99_99_Summer",
            )
    )

    # Rule init:
    habapp_rules.actors.shading.SlatValueSun(config)
    """

    def __init__(self, config: habapp_rules.actors.config.shading.SlatValueConfig) -> None:
        """Init SlatValueSun.

        Args:
            config: configuration of slat value

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationException: if configuration is not valid
        """
        self._config = config
        HABApp.Rule.__init__(self)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.slat_value.name)

        # slat characteristics
        self._slat_characteristic_active = self._config.parameter.elevation_slat_characteristic_summer if self._config.items.summer is not None and self._config.items.summer.is_on() else self._config.parameter.elevation_slat_characteristic

        # callbacks
        self._config.items.sun_elevation.listen_event(self._cb_elevation, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.summer is not None:
            self._config.items.summer.listen_event(self._cb_summer_winter, HABApp.openhab.events.ItemStateChangedEventFilter())
        self.run.soon(self.__send_slat_value)

        self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with name '{self.rule_name}' was successful.")

    def __get_slat_value(self, elevation: float) -> float:
        """Get slat value for given elevation.

        Args:
            elevation: elevation of the sun

        Returns:
            slat value
        """
        if elevation >= self._slat_characteristic_active[-1].elevation:
            return self._slat_characteristic_active[-1].slat_value
        if elevation < self._slat_characteristic_active[0].elevation:
            return self._slat_characteristic_active[0].slat_value

        # no cover because of loop does not finish, but is handled with the two if statements above
        return next(config for idx, config in enumerate(self._slat_characteristic_active) if config.elevation <= elevation < self._slat_characteristic_active[idx + 1].elevation).slat_value  # pragma: no cover

    def __send_slat_value(self) -> None:
        """Send slat value to OpenHAB item."""
        if self._config.items.sun_elevation.value is None:
            return
        slat_value = self.__get_slat_value(self._config.items.sun_elevation.value)

        if self._config.items.slat_value.value != slat_value:
            self._config.items.slat_value.oh_send_command(slat_value)

    def _cb_elevation(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa: ARG002
        """Callback which is called if sun elevation changed.

        Args:
            event: elevation event
        """
        self.__send_slat_value()

    def _cb_summer_winter(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is called if summer / winter changed.

        Args:
            event: summer / winter event
        """
        self._slat_characteristic_active = self._config.parameter.elevation_slat_characteristic_summer if event.value == "ON" else self._config.parameter.elevation_slat_characteristic
        self.__send_slat_value()


class ReferenceRun(HABApp.Rule):
    """Rule to trigger a reference run for blinds every month.

    # Items:
    Switch      trigger_run         "trigger reference run"
    DateTime    last_run            "last run"
    String      presence_state      "Presence state"

    # Config
    config = habapp_rules.actors.config.shading.ReferenceRunConfig(
            items=habapp_rules.actors.config.shading.ReferenceRunItems(
                trigger_run="trigger_run",
                presence_state="presence_state",
                last_run="last_run",
            )
    )

    # Rule init:
    habapp_rules.actors.shading.ReferenceRun(config)
    """

    def __init__(self, config: habapp_rules.actors.config.shading.ReferenceRunConfig) -> None:
        """Init ReferenceRun.

        Args:
            config: configuration of reference run rule
        """
        self._config = config
        HABApp.Rule.__init__(self)

        self._config.items.presence_state.listen_event(self._cb_presence_state, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _cb_presence_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is called if presence state changed.

        Args:
            event: presence state event
        """
        if event.value == habapp_rules.system.PresenceState.ABSENCE.value:
            last_run = self._config.items.last_run.value or datetime.datetime.min
            current_time = datetime.datetime.now()

            if last_run.year < current_time.year or last_run.month < current_time.month:
                self._config.items.trigger_run.oh_send_command("ON")
                self._config.items.last_run.oh_send_command(current_time)
