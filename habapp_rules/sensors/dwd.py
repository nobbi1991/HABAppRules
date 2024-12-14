"""DWD rules."""

import dataclasses
import datetime
import logging
import re
import typing

import HABApp

import habapp_rules.actors.state_observer
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.sensors.config.dwd

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class DwdItems:
    """Dataclass for DWD items needed by DwdWindAlarm."""

    description: HABApp.openhab.items.StringItem
    warn_type: HABApp.openhab.items.StringItem
    severity: HABApp.openhab.items.StringItem
    start_time: HABApp.openhab.items.DatetimeItem
    end_time: HABApp.openhab.items.DatetimeItem

    SEVERITY_MAPPING: typing.ClassVar = {"NULL": 0, "Minor": 1, "Moderate": 2, "Severe": 3, "Extreme": 4}

    @classmethod
    def from_prefix(cls, prefix: str) -> "DwdItems":
        """Init DwdItems from prefix.

        Args:
            prefix: common prefix of all DWD items

        Returns:
            Dataclass with all needed DWD items
        """
        description = HABApp.openhab.items.StringItem.get_item(f"{prefix}_description")
        warn_type = HABApp.openhab.items.StringItem.get_item(f"{prefix}_type")
        severity = HABApp.openhab.items.StringItem.get_item(f"{prefix}_severity")
        start_time = HABApp.openhab.items.DatetimeItem.get_item(f"{prefix}_start_time")
        end_time = HABApp.openhab.items.DatetimeItem.get_item(f"{prefix}_end_time")

        return cls(description, warn_type, severity, start_time, end_time)

    @property
    def severity_as_int(self) -> int:
        """Get severity as integer.

        Returns:
            severity as integer value
        """
        return self.SEVERITY_MAPPING.get(self.severity.value, 0)


class DwdWindAlarm(habapp_rules.core.state_machine_rule.StateMachineRule):
    """Rule for setting wind alarm by DWD warnings.

    # Items:
    Switch      I26_99_wind_alarm               "Wind alarm"
    Switch      I26_99_wind_alarm_manual        "Wind alarm manual"
    String      I26_99_wind_alarm_state         "Wind alarm state"

    String      I26_99_warning_1_severity       "Severity"              {channel="dwdunwetter:dwdwarnings:ingolstadt:severity1"}
    String      I26_99_warning_1_description    "Description"           {channel="dwdunwetter:dwdwarnings:ingolstadt:description1"}
    DateTime    I26_99_warning_1_start_time     "valid from"            {channel="dwdunwetter:dwdwarnings:ingolstadt:onset1"}
    DateTime    I26_99_warning_1_end_time       "valid till"            {channel="dwdunwetter:dwdwarnings:ingolstadt:expires1"}
    String      I26_99_warning_1_type           "Type"                  {channel="dwdunwetter:dwdwarnings:ingolstadt:event1"}

    String      I26_99_warning_2_severity       "Severity"              {channel="dwdunwetter:dwdwarnings:ingolstadt:severity2"}
    String      I26_99_warning_2_description    "Description"           {channel="dwdunwetter:dwdwarnings:ingolstadt:description2"}
    DateTime    I26_99_warning_2_start_time     "valid from"            {channel="dwdunwetter:dwdwarnings:ingolstadt:onset2"}
    DateTime    I26_99_warning_2_end_time       "valid till"            {channel="dwdunwetter:dwdwarnings:ingolstadt:expires2"}
    String      I26_99_warning_2_type           "Type"                  {channel="dwdunwetter:dwdwarnings:ingolstadt:event2"}

    # Config
    config = habapp_rules.sensors.config.dwd.WindAlarmConfig(
            items=habapp_rules.sensors.config.dwd.WindAlarmItems(
                    wind_alarm="I26_99_wind_alarm",
                    manual="I26_99_wind_alarm_manual",
                    state="I26_99_wind_alarm_state"
            ),
            parameter=habapp_rules.sensors.config.dwd.WindAlarmParameter(

            )
    )

    # Rule init:
    habapp_rules.sensors.dwd.DwdWindAlarm(config)
    """

    states: typing.ClassVar = [{"name": "Manual"}, {"name": "Hand", "timeout": 20 * 3600, "on_timeout": "_auto_hand_timeout"}, {"name": "Auto", "initial": "Init", "children": [{"name": "Init"}, {"name": "On"}, {"name": "Off"}]}]

    trans: typing.ClassVar = [
        {"trigger": "manual_on", "source": ["Auto", "Hand"], "dest": "Manual"},
        {"trigger": "manual_off", "source": "Manual", "dest": "Auto"},
        {"trigger": "hand", "source": "Auto", "dest": "Hand"},
        {"trigger": "wind_alarm_start", "source": "Auto_Off", "dest": "Auto_On"},
        {"trigger": "wind_alarm_end", "source": "Auto_On", "dest": "Auto_Off"},
    ]

    def __init__(self, config: habapp_rules.sensors.config.dwd.WindAlarmConfig) -> None:
        """Init of DWD wind alarm object.

        Args:
            config: config for DWD wind alarm rule

        Raises:
            TypeError: if type of hand_timeout is not supported
        """
        self._config = config
        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.wind_alarm.name)

        self._items_dwd = [DwdItems.from_prefix(f"{self._config.parameter.dwd_item_prefix}{idx + 1}") for idx in range(self._config.parameter.number_dwd_objects)]

        # init state machine
        self._previous_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(
            model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state"
        )  # this function is missing!

        self._wind_alarm_observer = habapp_rules.actors.state_observer.StateObserverSwitch(self._config.items.wind_alarm.name, self._cb_hand, self._cb_hand)

        self._set_timeouts()
        self._set_initial_state()

        # callbacks
        self._config.items.manual.listen_event(self._cb_manual, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.hand_timeout is not None:
            self._config.items.hand_timeout.listen_event(self._cb_hand_timeout, HABApp.openhab.events.ItemStateChangedEventFilter())

        self.run.at(self.run.trigger.interval(None, 300), self._cb_cyclic_check)

    def _get_initial_state(self, default_value: str = "") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        if self._config.items.manual.is_on():
            return "Manual"
        if self._wind_alarm_active():
            return "Auto_On"
        return "Auto_Off"

    def _get_hand_timeout(self) -> int:
        """Get value of hand timeout.

        Returns:
            hand timeout in seconds (0 is no timeout)
        """
        if self._config.items.hand_timeout is not None:
            if (item_value := self._config.items.hand_timeout.value) is None:
                self._instance_logger.warning("The value of the hand timeout item is None. Will use 24 hours as default!")
                return 24 * 3600
            return item_value
        return self._config.parameter.hand_timeout

    def _set_timeouts(self) -> None:
        """Set timeouts."""
        self.state_machine.get_state("Hand").timeout = self._get_hand_timeout()

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item and other states.

        This should method should be set to "after_state_change" of the state machine.
        """
        if self.state != self._previous_state:
            super()._update_openhab_state()
            self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

            if self.state == "Auto_On" and self._wind_alarm_observer.value is not True:
                self._wind_alarm_observer.send_command("ON")
            elif self.state == "Auto_Off" and self._wind_alarm_observer.value is not False:
                self._wind_alarm_observer.send_command("OFF")

            self._previous_state = self.state

    def on_enter_Auto_Init(self) -> None:  # noqa: N802
        """Is called on entering of init state."""
        self._set_initial_state()

    def _cb_hand(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:  # noqa: ARG002
        """Callback, which is triggered by the state observer if a manual change was detected.

        Args:
            event: original trigger event
        """
        self.hand()

    def _cb_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the manual switch has a state change event.

        Args:
            event: trigger event
        """
        if event.value == "ON":
            self.manual_on()
        else:
            self.manual_off()

    def _cb_hand_timeout(self, _: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if the timeout item changed."""
        self._set_timeouts()

    def _wind_alarm_active(self) -> bool:
        """Check if wind alarm is active.

        Returns:
            True if active, False if not
        """
        for dwd_items in self._items_dwd:
            if dwd_items.warn_type.value in {"BÖEN", "WIND", "STURM", "GEWITTER"}:
                speed_values = [int(value) for value in re.findall(r"\b(\d+)\s*km/h\b", dwd_items.description.value)]
                if not speed_values:
                    continue

                if max(speed_values) >= self._config.parameter.threshold_wind_speed and dwd_items.severity_as_int >= self._config.parameter.threshold_severity and dwd_items.start_time.value < datetime.datetime.now() < dwd_items.end_time.value:
                    return True
        return False

    def _cb_cyclic_check(self) -> None:
        """Callback to check if wind alarm is active. This should be called cyclic every few minutes."""
        if self.state not in {"Auto_On", "Auto_Off"}:
            return

        if self._wind_alarm_active() and self.state != "Auto_On":
            self.wind_alarm_start()

        elif not self._wind_alarm_active() and self.state != "Auto_Off":
            self.wind_alarm_end()
