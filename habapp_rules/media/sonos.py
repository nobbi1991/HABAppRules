import logging
import typing

import HABApp
import HABApp.core.events
from HABApp.openhab.definitions import ThingStatusEnum

import habapp_rules.actors.state_observer
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.media.config.sonos
from habapp_rules.core.helper import send_if_different
from habapp_rules.media.config.sonos import ContentLineIn, ContentPlayUri, ContentTuneIn, KnownContentBase

LOGGER = logging.getLogger(__name__)


class Sonos(habapp_rules.core.state_machine_rule.StateMachineRule):  # TODO think about sonos without switch
    states: typing.ClassVar = [
        {"name": "PowerOff"},
        {"name": "Starting"},
        {"name": "Standby"},
        {
            "name": "Playing",
            "initial": "Init",
            "children": [
                {"name": "Init"},
                {"name": "UnknownContent"},
                {"name": "TuneIn"},
                {"name": "PlayUri"},
                {"name": "LineIn"},
            ],
        },
    ]

    trans: typing.ClassVar = [
        # power switch
        {"trigger": "power_on", "source": "PowerOff", "dest": "Starting"},
        {"trigger": "power_off", "source": ["Starting", "Standby", "Playing"], "dest": "PowerOff"},
        # sonos thing
        {"trigger": "thing_online", "source": "Starting", "dest": "Standby"},
        # player
        {"trigger": "player_start", "source": "Standby", "dest": "Playing"},
        {"trigger": "player_end", "source": "Playing", "dest": "Standby"},
        # content changed
        {"trigger": "content_changed", "source": ["Playing_UnknownContent", "Playing_TuneIn", "Playing_PlayUri", "Playing_LineIn"], "dest": "Playing_Init"},
    ]

    def __init__(self, config: habapp_rules.media.config.sonos.SonosConfig) -> None:
        """Initialize sonos rule.

        Args:
            config: config
        """
        self._config = config

        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.sonos_player.name)

        # volume
        self._volume_observer = habapp_rules.actors.state_observer.StateObserverDimmer(self._config.items.sonos_volume.name, cb_change=self._cb_volume_changed) if self._config.items.sonos_volume is not None else None
        self._countdown_volume_lock = self.run.countown(self._cb_countdown_volume_lock, self._config.parameter.lock_time_volume) if self._config.parameter.lock_time_volume is not None else None
        self._volume_locked = False

        # init state machine
        self._previous_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_initial_state()

        # callbacks
        self._config.items.power_switch.listen_event(self._cb_power_switch, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.sonos_thing.listen_event(self._cb_thing, HABApp.core.events.EventFilter(HABApp.openhab.events.ThingStatusInfoChangedEvent))
        self._config.items.sonos_player.listen_event(self._cb_player, HABApp.openhab.events.ItemStateChangedEventFilter())

        if self._config.items.tune_in_station_id is not None:
            self._config.items.tune_in_station_id.listen_event(self._cb_tune_in_station_id, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.current_track_uri is not None:
            self._config.items.current_track_uri.listen_event(self._cb_current_track_uri, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.line_in is not None:
            self._config.items.line_in.listen_event(self._cb_line_in, HABApp.openhab.events.ItemStateChangedEventFilter())

        # log init finished
        self._instance_logger.info(self.get_initial_log_message())

    def _get_initial_state(self, default_value: str = "") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        if not self._config.items.power_switch.is_on():
            return "PowerOff"
        if self._config.items.sonos_thing.status != ThingStatusEnum.ONLINE:
            return "Starting"
        if self._config.items.sonos_player.value == "PLAY":
            return "Playing_Init"
        return "Standby"

    def on_enter_Playing_Init(self) -> None:  # noqa: N802
        """Go to child state if playing_init state is entered."""
        if self._config.items.tune_in_station_id is not None and self._config.items.tune_in_station_id.value not in {"", None}:
            self._set_state("Playing_TuneIn")
            return

        if self._config.items.current_track_uri is not None and self._config.items.current_track_uri.value in self._config.parameter.get_known_play_uris():
            self._set_state("Playing_PlayUri")
            return

        if self._config.items.line_in is not None and self._config.items.line_in.is_on():
            self._set_state("Playing_LineIn")
            return

        self._set_state("Playing_UnknownContent")

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
        """Set output states."""
        display_str = "Unknown"

        if self.state == "PowerOff":
            display_str = "Off"
        elif self.state == "Starting":
            display_str = "Starting"
        elif self.state == "Standby":
            display_str = "Standby"
        elif self.state.startswith("Playing"):
            known_content = self._check_if_known_content()
            display_str = known_content.display_text if known_content is not None else "Playing"

        if self._config.items.display_string is not None:
            send_if_different(self._config.items.display_string, display_str)

    def _check_if_known_content(self) -> ContentTuneIn | ContentPlayUri | ContentLineIn | None:
        """Check if the current content is a known content.

        Returns:
            known content object if known, otherwise None
        """
        if self._config.items.tune_in_station_id is not None and str(self._config.items.tune_in_station_id.value).isnumeric():  # noqa: SIM102
            if known_content := next((content for content in self._config.parameter.known_content if isinstance(content, ContentTuneIn) and content.tune_in_id == int(self._config.items.tune_in_station_id.value)), None):
                return known_content

        if self._config.items.current_track_uri is not None:  # noqa: SIM102
            if known_content := next((content for content in self._config.parameter.known_content if isinstance(content, ContentPlayUri) and content.uri == self._config.items.current_track_uri.value), None):
                return known_content

        if self._config.items.line_in is not None and self._config.items.line_in.is_on() and (known_content := next((content for content in self._config.parameter.known_content if isinstance(content, ContentLineIn)), None)):
            return known_content

        return None

    def _set_start_volume(self, known_content: KnownContentBase | None) -> None:
        """Set start volume."""
        if self._volume_locked:
            return

        start_volume = known_content.start_volume if known_content else None

        if start_volume is None:
            if self.state == "Playing_TuneIn":
                start_volume = self._config.parameter.start_volume_tune_in
            elif self.state == "Playing_LineIn":
                start_volume = self._config.parameter.start_volume_line_in
            elif self.state == "Playing_UnknownContent":
                start_volume = self._config.parameter.start_volume_unknown

        if start_volume is not None:
            self._volume_observer.send_command(start_volume)

    def _cb_power_switch(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the power switch was changed.

        Args:
            event: event which triggered this event
        """
        if event.value == "ON":
            self.power_on()
        else:
            self.power_off()

    def _cb_thing(self, event: HABApp.openhab.events.ThingStatusInfoChangedEvent) -> None:
        """Callback if the sonos thing state changed.

        Args:
            event: event which triggered this event
        """
        if event.status == ThingStatusEnum.ONLINE:
            self.thing_online()

    def _cb_player(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the player / controller changed the state.

        Args:
            event: event which triggered this event
        """
        if event.value == "PLAY":
            self.player_start()
        else:
            self.player_end()

    def _cb_volume_changed(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa: ARG002
        """Callback if the volume changed.

        Args:
            event: event which triggered this event
        """
        if self._countdown_volume_lock is not None:
            self._volume_locked = True
            self._countdown_volume_lock.reset()

    def _cb_countdown_volume_lock(self) -> None:
        self._volume_locked = False

    def _cb_tune_in_station_id(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the statin id changed.

        Args:
            event: event which triggered this event
        """
        if event.value and self.state.startswith("Playing"):
            self.content_changed()

    def _cb_current_track_uri(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the track URI changed.

        Args:
            event: event which triggered this event
        """
        if event.value and self.state.startswith("Playing"):
            self.content_changed()

    def _cb_line_in(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the line in state changed.

        Args:
            event: event which triggered this event
        """
        if event.value == "ON" and self.state.startswith("Playing"):
            self.content_changed()
