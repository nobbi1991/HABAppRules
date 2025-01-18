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

KNOWN_CONTENT_TYPES = ContentTuneIn | ContentPlayUri | ContentLineIn


class Sonos(habapp_rules.core.state_machine_rule.StateMachineRule):  # TODO think about sonos without switch
    states: typing.ClassVar = [
        {"name": "PowerOff"},
        {"name": "Booting", "timeout": 300, "on_timeout": "timeout_booting"},
        {"name": "Standby"},
        {"name": "Starting", "timeout": 20, "on_timeout": "timeout_starting"},
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
        {"trigger": "power_on", "source": "PowerOff", "dest": "Booting"},
        {"trigger": "power_off", "source": ["Booting", "Standby", "Playing"], "dest": "PowerOff"},
        {"trigger": "timeout_booting", "source": "Booting", "dest": "PowerOff"},
        # sonos thing
        {"trigger": "thing_online", "source": "Booting", "dest": "Standby"},
        # player
        {"trigger": "player_start", "source": ["Standby", "Starting"], "dest": "Playing"},
        {"trigger": "player_end", "source": ["Playing"], "dest": "Standby"},  # todo: check if "Starting" should be added to source
        # content changed
        {"trigger": "content_changed", "source": ["Standby", "Starting", "Playing"], "dest": "Starting"},
        # starting
        {"trigger": "timeout_starting", "source": "Starting", "dest": "Standby"},
    ]

    def __init__(self, config: habapp_rules.media.config.sonos.SonosConfig) -> None:
        """Initialize sonos rule.

        Args:
            config: config
        """
        self._config = config

        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.sonos_player.name)

        # favorite id
        self._started_through_favorite_id = False
        self._favorite_id_observer = habapp_rules.actors.state_observer.StateObserverNumber(self._config.items.favorite_id.name, cb_manual=self._cb_favorite_id) if self._config.items.favorite_id is not None else None

        # volume
        self._volume_observer = habapp_rules.actors.state_observer.StateObserverDimmer(self._config.items.sonos_volume.name, cb_change=self._cb_volume_changed) if self._config.items.sonos_volume is not None else None
        self._countdown_volume_lock = self.run.countown(self._cb_countdown_volume_lock, self._config.parameter.lock_time_volume) if self._config.parameter.lock_time_volume is not None else None
        self._volume_locked = False

        # init state machine
        self._previous_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_timeouts()
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

    def _set_timeouts(self) -> None:
        """Set timeouts of state machine."""
        self.state_machine.states["Booting"].timeout = self._config.parameter.booting_timeout
        self.state_machine.states["Starting"].timeout = self._config.parameter.starting_timeout

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
            return "Booting"
        if self._config.items.sonos_player.value == "PLAY":
            return "Playing_Init"
        return "Standby"

    def on_enter_Playing_Init(self) -> None:  # noqa: N802
        """Go to child state if playing_init state is entered."""
        if self._config.items.current_track_uri.value.startswith("x-file-cifs:"):  # todo add to enum?! and reuse it
            self._set_state("Playing_PlayUri")

        elif "tunein" in self._config.items.current_track_uri.value:
            self._set_state("Playing_TuneIn")

        elif self._config.items.current_track_uri.value.startswith("x-sonos-htastream:"):
            self._set_state("Playing_LineIn")

        else:
            self._set_state("Playing_UnknownContent")

    def on_enter_Starting(self) -> None:  # noqa: N802
        if self._config.items.sonos_player.value == "PLAY":
            self.player_start()

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
        known_content = self._check_if_known_content() if self.state.startswith("Playing_") else None

        self._set_start_volume(known_content)
        self._set_outputs_display_string(known_content)
        self._set_outputs_favorite_id(known_content)

    def _set_outputs_display_string(self, known_content: KNOWN_CONTENT_TYPES | None = None) -> None:
        """Set display string."""
        display_str = "Unknown"

        if self.state == "PowerOff":
            display_str = "Off"
        elif self.state == "Booting":
            display_str = "Booting"
        elif self.state == "Standby":
            display_str = "Standby"
        elif self.state == "Starting":
            display_str = "Starting"
        elif self.state.startswith("Playing_"):
            display_str = known_content.display_text if known_content is not None else "Playing"
        if self._config.items.display_string is not None:
            send_if_different(self._config.items.display_string, display_str)

    def _set_outputs_favorite_id(self, known_content: KNOWN_CONTENT_TYPES | None = None) -> None:
        """Set favorite id."""
        if self._favorite_id_observer is None:
            return

        if self.state == "Standby" and self._previous_state.startswith("Playing_"):
            self._favorite_id_observer.send_command(0)

        elif self.state == "Standby" and self._previous_state == "Booting" and self._started_through_favorite_id:
            self._set_favorite_content(self._get_favorite_content())

        elif self.state.startswith("Playing_"):
            fav_id = known_content.favorite_id if known_content is not None else -1
            self._favorite_id_observer.send_command(fav_id)

        elif self.state == "PowerOff":
            self._favorite_id_observer.send_command(0)

    def _check_if_known_content(self) -> KNOWN_CONTENT_TYPES | None:
        """Check if the current content is a known content.

        Returns:
            known content object if known, otherwise None
        """
        if self._config.items.current_track_uri.value.startswith("x-file-cifs:"):
            if known_content := next((content for content in self._config.parameter.known_content if isinstance(content, ContentPlayUri) and content.uri == self._config.items.current_track_uri.value), None):
                return known_content

        elif "tunein" in self._config.items.current_track_uri.value:
            if known_content := next((content for content in self._config.parameter.known_content if isinstance(content, ContentTuneIn) and content.tune_in_id == int(self._config.items.tune_in_station_id.value)), None):
                return known_content

        elif (
            self._config.items.current_track_uri.value.startswith("x-sonos-htastream:")
            and self._config.items.line_in.is_on()
            and (known_content := next((content for content in self._config.parameter.known_content if isinstance(content, ContentLineIn)), None))
        ):
            return known_content

        return None

    def _set_start_volume(self, known_content: KnownContentBase | None) -> None:
        """Set start volume."""
        if self._volume_locked or not self.state.startswith("Playing_"):
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

    def _get_favorite_content(self, fav_id: int | None = None) -> ContentTuneIn | ContentPlayUri | None:
        """Get favorite content instance by favorite id."

        Args:
            fav_id: favorite ID. If not given, the value will be taken from the OH item

        Returns:
            instance of ContentTuneIn or ContentPlayUri (or None if not found)
        """
        fav_id = fav_id if fav_id is not None else self._config.items.favorite_id.value
        return next((content for content in self._config.parameter.known_content if content.favorite_id == fav_id), None)

    def _set_favorite_content(self, fav_content: ContentTuneIn | ContentPlayUri) -> None:
        """Set favorite content.

        Args:
            fav_content: instance of ContentTuneIn or ContentPlayUri which should be set
        """
        if isinstance(fav_content, ContentTuneIn):
            self._config.items.tune_in_station_id.oh_send_command(fav_content.tune_in_id)
        elif isinstance(fav_content, ContentPlayUri):
            self._config.items.play_uri.oh_send_command(str(fav_content.uri))

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

    def _cb_favorite_id(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the favorite id changed.

        Args:
            event: event which triggered this event
        """
        if event.value == -1:  # unknown content
            return

        if event.value == 0:  # fav id 0 -> stop
            if self.state.startswith("Playing_"):
                self._config.items.sonos_player.oh_send_command("PAUSE")
            elif self.state == "Starting":
                self.player_end()
            return

        fav_content = self._get_favorite_content(event.value)

        if fav_content is None:
            self._instance_logger.warning(f"Favorite ID {event.value} is not known.")
            return

        if self.state.startswith("Playing_"):
            self._config.items.sonos_player.oh_send_command("PAUSE")

        if self.state.startswith("Playing_") or self.state == "Standby":
            self.content_changed()
            self._set_favorite_content(fav_content)

        if self.state == "PowerOff":
            self._started_through_favorite_id = True
            self._config.items.power_switch.oh_send_command("ON")

    def _cb_tune_in_station_id(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the statin id changed.

        Args:
            event: event which triggered this event
        """
        if (event.value and self.state.startswith("Playing_")) or self.state == "Standby":
            self.content_changed()

    def _cb_current_track_uri(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the track URI changed.

        Args:
            event: event which triggered this event
        """
        if (event.value and self.state.startswith("Playing_")) or self.state == "Standby" and "tunein" not in event.value.lower():
            self.content_changed()

    def _cb_line_in(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback if the line in state changed.

        Args:
            event: event which triggered this event
        """
        if (event.value == "ON" and self.state.startswith("Playing_")) or self.state == "Standby":
            self.content_changed()
