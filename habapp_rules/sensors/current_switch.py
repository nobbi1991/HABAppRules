"""current switch rules."""

from typing import TYPE_CHECKING

import HABApp
from HABApp.openhab.events import ItemStateChangedEvent
from HABApp.openhab.events.event_filters import ItemStateChangedEventFilter

from habapp_rules.core.helper import send_if_different
from habapp_rules.sensors.config.current_switch import CurrentSwitchConfig

if TYPE_CHECKING:
    from HABApp.rule.scheduler.job_ctrl import CountdownJobControl


class CurrentSwitch(HABApp.Rule):
    """Rules class which manages a switch based on electrical current values.

    # Items:
    Number    Current              "Current"
    Switch    Something_is_ON      "Something is ON"

    # Config:
    config = CurrentSwitchConfig(
            items = CurrentSwitchItems(
                    current="Current",
                    switch="Something_is_ON"
            )
    )

    # Rule init:
    CurrentSwitch(config)
    """

    def __init__(self, config: CurrentSwitchConfig) -> None:
        """Init current switch rule.

        Args:
            config: config for current switch rule
        """
        HABApp.Rule.__init__(self)
        self._config = config
        self._extended_countdown: CountdownJobControl | None = self.run.countdown(self._config.parameter.extended_time, self._countdown_end) if self._config.parameter.extended_time else None

        self._check_current_and_set_switch(self._config.items.current.value)
        self._config.items.current.listen_event(self._cb_current_changed, ItemStateChangedEventFilter())

    def _countdown_end(self) -> None:
        """Callback which is called if the extended countdown ended."""
        send_if_different(self._config.items.switch, "OFF")

    def _check_current_and_set_switch(self, current: float | None) -> None:
        """Check if current is above the threshold and set switch.

        Args:
            current: current value which should be checked
        """
        if current is None:
            return

        current_above_threshold = current > self._config.parameter.threshold

        if self._config.parameter.extended_time and self._extended_countdown is not None:
            if current_above_threshold:
                self._extended_countdown.stop()
                send_if_different(self._config.items.switch, "ON")

            elif not current_above_threshold and self._config.items.switch.is_on():
                # start or reset the countdown
                self._extended_countdown.reset()

        else:
            # extended time is not active
            send_if_different(self._config.items.switch, "ON" if current_above_threshold else "OFF")

    def _cb_current_changed(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is called if the current value changed.

        Args:
            event: event, which triggered this callback
        """
        self._check_current_and_set_switch(event.value)
