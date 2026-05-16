"""Rule to detect presence or absence."""

import logging
import typing

from HABApp.core.events import ValueChangeEventFilter
from HABApp.openhab.events import ItemStateChangedEvent
from HABApp.openhab.events.event_filters import ItemStateChangedEventFilter

from habapp_rules.core.helper import send_if_different
from habapp_rules.core.state_machine_rule import StateMachineRule, StateMachineWithTimeout
from habapp_rules.system import PresenceState
from habapp_rules.system.config.presence import PresenceConfig

LOGGER = logging.getLogger(__name__)


class Presence(StateMachineRule):
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
    config = PresenceConfig(
            items=PresenceItems(
                    presence="I01_00_Presence",
                    leaving="I01_00_Leaving"
            )
    )

    # Rule init:
    Presence(config)
    """

    states: typing.ClassVar = [
        {"name": "Presence"},
        {"name": "Leaving", "timeout": 5 * 60, "on_timeout": "absence_detected"},  # leaving takes 5 minutes
        {"name": "Absence", "timeout": 1.5 * 24 * 3600, "on_timeout": "long_absence_detected"},  # switch to long absence after 1.5 days
        {"name": "LongAbsence"},
    ]

    trans: typing.ClassVar = [
        {"trigger": "presence_detected", "source": ["Absence", "LongAbsence"], "dest": "Presence"},
        {"trigger": "leaving_detected", "source": ["Presence", "Absence", "LongAbsence"], "dest": "Leaving"},
        {"trigger": "abort_leaving", "source": "Leaving", "dest": "Presence"},
        {"trigger": "absence_detected", "source": ["Presence", "Leaving"], "dest": "Absence"},
        {"trigger": "long_absence_detected", "source": "Absence", "dest": "LongAbsence"},
    ]

    def __init__(self, config: PresenceConfig) -> None:
        """Init of Presence object.

        Args:
            config: config for presence state
        """
        self._config = config
        StateMachineRule.__init__(self, config.items.state, config.items.presence.name)

        # init state machine
        self.state_machine = StateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state", initial=self._get_initial_state())

        # add callbacks
        self._config.items.leaving.listen_event(self._cb_leaving, ItemStateChangedEventFilter())
        self._config.items.presence.listen_event(self._cb_presence, ItemStateChangedEventFilter())
        for door_item in self._config.items.outdoor_doors:
            door_item.listen_event(self._cb_outside_door, ValueChangeEventFilter())
        for phone_item in self._config.items.phones:
            phone_item.listen_event(self._cb_phone, ValueChangeEventFilter())

        self.__phone_absence_countdown = self.run.countdown(20 * 60, self.__set_leaving_through_phone)
        self._post_init()

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
        send_if_different(self._config.items.presence, target_value)
        send_if_different(self._config.items.leaving, "ON" if self.state == PresenceState.LEAVING.value else "OFF")

    def _cb_outside_door(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is called if any outside door changed state.

        Args:
            event: state change event of door item
        """
        if event.value == "OPEN" and self.state not in {PresenceState.PRESENCE.value, PresenceState.LEAVING.value}:
            self._instance_logger.debug(f"Presence detected by door ({event.name})")
            self.trigger("presence_detected")

    def _cb_leaving(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is called if leaving item changed state.

        Args:
            event: Item state change event of leaving item
        """
        if event.value == "ON" and self.state in {PresenceState.PRESENCE.value, PresenceState.ABSENCE.value, PresenceState.LONG_ABSENCE.value}:
            self._instance_logger.debug("Start leaving through leaving switch")
            self.trigger("leaving_detected")
        if event.value == "OFF" and self.state == PresenceState.LEAVING.value:
            self._instance_logger.debug("Abort leaving through leaving switch")
            self.trigger("abort_leaving")

    def _cb_presence(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is called if presence item changed state.

        Args:
            event: Item state change event of presence item
        """
        if event.value == "ON" and self.state in {PresenceState.ABSENCE.value, PresenceState.LONG_ABSENCE.value}:
            self._instance_logger.debug("Presence was set manually by presence switch")
            self.trigger("presence_detected")
        elif event.value == "OFF" and self.state in {PresenceState.PRESENCE.value, PresenceState.LEAVING.value}:
            self._instance_logger.debug("Absence was set manually by presence switch")
            self.trigger("absence_detected")

    def _cb_phone(self, event: ItemStateChangedEvent) -> None:
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
                self.trigger("abort_leaving")

            if self.state in {PresenceState.ABSENCE.value, PresenceState.LONG_ABSENCE.value}:
                self._instance_logger.debug("Presence was set through first phone joined network")
                self.trigger("presence_detected")

        elif active_phones == 0 and event.value == "OFF":
            # last phone switched to OFF
            self.__phone_absence_countdown.reset()

    def __set_leaving_through_phone(self) -> None:
        """Set leaving detected if timeout expired."""
        if self.state == PresenceState.PRESENCE.value:
            self._instance_logger.debug("Leaving was set, because last phone left some time ago.")
            self.trigger("leaving_detected")
