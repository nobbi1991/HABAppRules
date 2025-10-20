"""Rule to detect presence or absence."""

import logging
import typing

import HABApp.openhab.events
import HABApp.util

import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system.config.presence
from habapp_rules.system import PresenceState

LOGGER = logging.getLogger(__name__)


class Presence(habapp_rules.core.state_machine_rule.StateMachineRule):
    """Rule class to manage the presence of a home.

    Hint: If you have some kind of guest-mode, use a guest-available switch as a phone to enable a persistent presence, also if all phones are not at home

    Example OpenHAB configuration:
    # KNX-things:
    Thing device T00_99_OpenHab_Presence "KNX OpenHAB Presence"{
        Type switch-control        : presence       "Presence"      [ ga="0/2/11+0/2/10"]
        Type switch-control        : leaving        "Leaving"       [ ga="0/2/21+0/2/20"]
    }

    # Items:
    Switch    I01_00_Presence    "Presence"         <presence>    (G00_00_rrd4j)    ["Status", "Presence"]    {channel="knx:device:bridge:T00_99_OpenHab_Presence:presence"}
    Switch    I01_00_Leaving     "Leaving"          <leaving>                                                 {channel="knx:device:bridge:T00_99_OpenHab_Presence:leaving"}

    # Config:
    config = habapp_rules.system.config.presence.PresenceConfig(
            items=habapp_rules.system.config.presence.PresenceItems(
                    presence="I01_00_Presence",
                    leaving="I01_00_Leaving"
            )
    )

    # Rule init:
    habapp_rules.system.presence.Presence(config)
    """

    states: typing.ClassVar = [
        {"name": "presence"},
        {"name": "leaving", "timeout": 5 * 60, "on_timeout": "absence_detected"},  # leaving takes 5 minutes
        {"name": "absence", "timeout": 1.5 * 24 * 3600, "on_timeout": "long_absence_detected"},  # switch to long absence after 1.5 days
        {"name": "long_absence"},
    ]

    trans: typing.ClassVar = [
        {"trigger": "presence_detected", "source": ["absence", "long_absence"], "dest": "presence"},
        {"trigger": "leaving_detected", "source": ["presence", "absence", "long_absence"], "dest": "leaving"},
        {"trigger": "abort_leaving", "source": "leaving", "dest": "presence"},
        {"trigger": "absence_detected", "source": ["presence", "leaving"], "dest": "absence"},
        {"trigger": "long_absence_detected", "source": "absence", "dest": "long_absence"},
    ]

    def __init__(self, config: habapp_rules.system.config.presence.PresenceConfig) -> None:
        """Init of Presence object.

        Args:
            config: config for presence detection
        """
        self._config = config
        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, config.items.presence.name)

        # init state machine
        self.state_machine = habapp_rules.core.state_machine_rule.StateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_initial_state()

        # add callbacks
        self._config.items.leaving.listen_event(self._cb_leaving, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.presence.listen_event(self._cb_presence, HABApp.openhab.events.ItemStateChangedEventFilter())
        for door_item in self._config.items.outdoor_doors:
            door_item.listen_event(self._cb_outside_door, HABApp.core.events.ValueChangeEventFilter())
        for phone_item in self._config.items.phones:
            phone_item.listen_event(self._cb_phone, HABApp.core.events.ValueChangeEventFilter())

        self.__phone_absence_countdown = self.run.countdown(20 * 60, self.__set_leaving_through_phone)
        self._instance_logger.debug(super().get_initial_log_message())

    def _get_initial_state(self, default_value: str = PresenceState.PRESENCE.value) -> str:
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            return correct state if it could be detected, if not return default value
        """
        phone_items = [phone for phone in self._config.items.phones if phone.value is not None]  # phones with valid state (not None)
        if phone_items:
            if any(item.value == "ON" for item in phone_items):
                return PresenceState.PRESENCE.value

            if self._config.items.presence.value == "ON":
                return PresenceState.LEAVING.value
            return PresenceState.LONG_ABSENCE.value if self._item_state.value == PresenceState.LONG_ABSENCE.value else PresenceState.ABSENCE.value

        if self._config.items.leaving.value == "ON":
            return PresenceState.LEAVING.value

        if self._config.items.presence.value == "ON":
            return PresenceState.PRESENCE.value

        if self._config.items.presence.value == "OFF":
            return PresenceState.LONG_ABSENCE.value if self._item_state.value == PresenceState.LONG_ABSENCE.value else PresenceState.ABSENCE.value

        return default_value

    def _update_openhab_state(self) -> None:
        """Extend _update_openhab state of base class to also update other OpenHAB items."""
        super()._update_openhab_state()
        self._instance_logger.info(f"Presence state changed to {self.state}")

        # update presence item
        target_value = "ON" if self.state in {PresenceState.PRESENCE.value, PresenceState.LEAVING.value} else "OFF"
        habapp_rules.core.helper.send_if_different(self._config.items.presence, target_value)
        habapp_rules.core.helper.send_if_different(self._config.items.leaving, "ON" if self.state == PresenceState.LEAVING.value else "OFF")

    def _cb_outside_door(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if any outside door changed state.

        Args:
            event: state change event of door item
        """
        if event.value == "OPEN" and self.state not in {PresenceState.PRESENCE.value, PresenceState.LEAVING.value}:
            self._instance_logger.debug(f"Presence detected by door ({event.name})")
            self.presence_detected()

    def _cb_leaving(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if leaving item changed state.

        Args:
            event: Item state change event of leaving item
        """
        if event.value == "ON" and self.state in {PresenceState.PRESENCE.value, PresenceState.ABSENCE.value, PresenceState.LONG_ABSENCE.value}:
            self._instance_logger.debug("Start leaving through leaving switch")
            self.leaving_detected()
        if event.value == "OFF" and self.state == PresenceState.LEAVING.value:
            self._instance_logger.debug("Abort leaving through leaving switch")
            self.abort_leaving()

    def _cb_presence(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if presence item changed state.

        Args:
            event: Item state change event of presence item
        """
        if event.value == "ON" and self.state in {PresenceState.ABSENCE.value, PresenceState.LONG_ABSENCE.value}:
            self._instance_logger.debug("Presence was set manually by presence switch")
            self.presence_detected()
        elif event.value == "OFF" and self.state in {PresenceState.PRESENCE.value, PresenceState.LEAVING.value}:
            self._instance_logger.debug("Absence was set manually by presence switch")
            self.absence_detected()

    def _cb_phone(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if a phone state changed.

        Args:
            event: Item state change event of phone item
        """
        active_phones = len([phone for phone in self._config.items.phones if phone.value == "ON"])
        if active_phones == 1 and event.value == "ON":
            # first phone switched to ON
            if self.__phone_absence_countdown.next_run_datetime:
                self.__phone_absence_countdown.stop()

            if self.state == PresenceState.LEAVING.value:
                self._instance_logger.debug("Leaving was aborted through first phone which came online")
                self.abort_leaving()

            if self.state in {PresenceState.ABSENCE.value, PresenceState.LONG_ABSENCE.value}:
                self._instance_logger.debug("Presence was set through first phone joined network")
                self.presence_detected()

        elif active_phones == 0 and event.value == "OFF":
            # last phone switched to OFF
            self.__phone_absence_countdown.reset()

    def __set_leaving_through_phone(self) -> None:
        """Set leaving detected if timeout expired."""
        if self.state == PresenceState.PRESENCE.value:
            self._instance_logger.debug("Leaving was set, because last phone left some time ago.")
            self.leaving_detected()
