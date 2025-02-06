"""Rules to for garden watering."""

import datetime
import logging

import HABApp

import habapp_rules.actors.config.irrigation
import habapp_rules.core.exceptions
import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class Irrigation(HABApp.Rule):
    """Rule for easy irrigation control.

    # Items:
    Switch     I999_valve                   "Valve state"           {channel="some_channel_config"}
    Switch     I999_irrigation_active       "Irrigation active"
    Number     I999_irrigation_hour         "Start hour"
    Number     I999_irrigation_minute       "Start minute"
    Number     I999_irrigation_duration     "Duration"

    # Config:
    config = habapp_rules.actors.config.irrigation.IrrigationConfig(
            items=habapp_rules.actors.config.irrigation.IrrigationItems(
                    valve=HABApp.openhab.items.SwitchItem("I999_valve"),
                    active=HABApp.openhab.items.SwitchItem("I999_irrigation_active"),
                    hour=HABApp.openhab.items.NumberItem("I999_irrigation_hour"),
                    minute=HABApp.openhab.items.NumberItem("I999_irrigation_minute"),
                    duration=HABApp.openhab.items.NumberItem("I999_irrigation_duration"),
                )
        )

    # Rule init:
    habapp_rules.actors.irrigation.Irrigation(config)
    """

    def __init__(self, config: habapp_rules.actors.config.irrigation.IrrigationConfig) -> None:
        """Init of irrigation object.

        Args:
            config: config for the rule

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationException: if configuration is not correct
        """
        self._config = config
        HABApp.Rule.__init__(self)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.valve.name)

        self.run.soon(self._cb_set_valve_state)
        self.run.at(self.run.trigger.interval(None, 60), self._cb_set_valve_state)

        self._config.items.active.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.minute.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.hour.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.repetitions is not None:
            self._config.items.repetitions.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.brake is not None:
            self._config.items.brake.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with name '{self.rule_name}' was successful.")

    def _get_target_valve_state(self) -> bool:
        """Get target valve state, depending on the OpenHAB item states.

        Returns:
            True if valve should be on, otherwise False
        Raises:
            habapp_rules.core.exceptions.HabAppRulesError: if value for hour / minute / duration is not valid
        """
        if not self._config.items.active.is_on():
            return False

        if any(item.value is None for item in (self._config.items.hour, self._config.items.minute, self._config.items.duration)):
            self._instance_logger.warning(
                f"OpenHAB item values are not valid for hour / minute / duration. Will return False. See current values: hour={self._config.items.hour.value} | minute={self._config.items.minute.value} | duration={self._config.items.duration.value}"
            )
            return False

        repetitions = self._config.items.repetitions.value if self._config.items.repetitions else 0
        brake = int(self._config.items.brake.value) if self._config.items.brake else 0

        now = datetime.datetime.now()
        hour = int(self._config.items.hour.value)
        minute = int(self._config.items.minute.value)
        duration = int(self._config.items.duration.value)

        for idx in range(repetitions + 1):
            start_time = datetime.datetime.combine(date=now, time=datetime.time(hour, minute)) + datetime.timedelta(minutes=idx * (duration + brake))
            end_time = start_time + datetime.timedelta(minutes=duration)
            if self._is_in_time_range(start_time.time(), end_time.time(), now.time()):
                return True
        return False

    @staticmethod
    def _is_in_time_range(start_time: datetime.time, end_time: datetime.time, time_to_check: datetime.time) -> bool:
        """Check if a time is in a given range.

        Args:
            start_time: start time of the time range
            end_time: end time of the time range
            time_to_check: time, which should be checked

        Returns:
            True if the time, which should be checked is between start and stop time
        """
        if end_time < start_time:
            return start_time <= time_to_check or end_time > time_to_check
        return start_time <= time_to_check < end_time

    def _cb_set_valve_state(self, _: HABApp.openhab.events.ItemStateChangedEvent | None = None) -> None:
        """Callback to set the valve state, triggered by cyclic call or item event."""
        try:
            target_value = self._get_target_valve_state()
        except habapp_rules.core.exceptions.HabAppRulesError as exc:
            self._instance_logger.warning(f"Could not get target valve state, set it to false. Error: {exc}")
            target_value = False

        if self._config.items.valve.is_on() != target_value:
            self._instance_logger.info(f"Valve state changed to {target_value}")
            self._config.items.valve.oh_send_command("ON" if target_value else "OFF")
