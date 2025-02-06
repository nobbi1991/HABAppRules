"""Rule for evaluating a humidity sensor."""

import logging
import typing

import HABApp

import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.sensors.config.humidity

LOGGER = logging.getLogger(__name__)


class HumiditySwitch(habapp_rules.core.state_machine_rule.StateMachineRule):
    """Rule for setting humidity switch if high humidity or a high humidity change is detected."""

    states: typing.ClassVar = [
        {"name": "off"},
        {
            "name": "on",
            "initial": "HighHumidity",
            "children": [
                {"name": "HighHumidity"},
                {"name": "Extended", "timeout": 99, "on_timeout": "on_extended_timeout"},
            ],
        },
    ]

    trans: typing.ClassVar = [
        {"trigger": "high_humidity_start", "source": "off", "dest": "on"},
        {"trigger": "high_humidity_start", "source": "on_Extended", "dest": "on_HighHumidity"},
        {"trigger": "high_humidity_end", "source": "on_HighHumidity", "dest": "on_Extended"},
        {"trigger": "on_extended_timeout", "source": "on_Extended", "dest": "off"},
    ]

    def __init__(self, config: habapp_rules.sensors.config.humidity.HumiditySwitchConfig) -> None:
        """Init humidity rule.

        Args:
            config: config for humidity switch rule
        """
        self._config = config
        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.humidity.name)

        # init state machine
        self._previous_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_initial_state()

        self.state_machine.get_state("on_Extended").timeout = self._config.parameter.extended_time

        # register callbacks
        self._config.items.humidity.listen_event(self._cb_humidity, HABApp.openhab.events.ItemStateUpdatedEventFilter())

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item. This should method should be set to "after_state_change" of the state machine."""
        super()._update_openhab_state()
        self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

        self._set_output()
        self._previous_state = self.state

    def _set_output(self) -> None:
        """Set output."""
        target_state = "ON" if self.state in {"on_HighHumidity", "on_Extended"} else "OFF"
        habapp_rules.core.helper.send_if_different(self._config.items.output, target_state)

    def _get_initial_state(self, default_value: str = "initial") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        return "on" if self._check_high_humidity() else "off"

    def _check_high_humidity(self, humidity_value: float | None = None) -> bool:
        """Check if humidity is above threshold.

        Args:
            humidity_value: humidity value, which should be checked. If None, the value of the humidity item will be used

        Returns:
             if humidity is above threshold
        """
        if humidity_value is None:
            if self._config.items.humidity.value is None:
                return False
            humidity_value = self._config.items.humidity.value

        return humidity_value >= self._config.parameter.absolute_threshold

    def _cb_humidity(self, event: HABApp.openhab.events.ItemStateUpdatedEvent) -> None:
        """Callback, which is triggered if the humidity was updated.

        Args:
            event: trigger event
        """
        if self._check_high_humidity(event.value):
            self.high_humidity_start()
        else:
            self.high_humidity_end()
