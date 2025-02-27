"""current switch rules."""

from typing import TYPE_CHECKING

import HABApp

import habapp_rules.core.helper
import habapp_rules.sensors.config.current_switch

if TYPE_CHECKING:
    from eascheduler.jobs.job_countdown import CountdownJob  # pragma: no cover


class CurrentSwitch(HABApp.Rule):
    """Rules class to manage basic light states.

    # Items:
    Number    Current              "Current"
    Switch    Something_is_ON      "Something is ON"

    # Config:
    config = habapp_rules.sensors.config.current_switch.CurrentSwitchConfig(
            items = habapp_rules.actors.config.light.CurrentSwitchItems(
                    current="Current",
                    switch="Something_is_ON"
            )
    )

    # Rule init:
    habapp_rules.actors.power.CurrentSwitch(config)
    """

    def __init__(self, config: habapp_rules.sensors.config.current_switch.CurrentSwitchConfig) -> None:
        """Init current switch rule.

        Args:
            config: config for current switch rule
        """
        HABApp.Rule.__init__(self)
        self._config = config
        self._extended_countdown: CountdownJob | None = (
            self.run.countdown(self._config.parameter.extended_time, habapp_rules.core.helper.send_if_different, item=self._config.items.switch, value="OFF") if self._config.parameter.extended_time else None
        )

        self._check_current_and_set_switch(self._config.items.current.value)
        self._config.items.current.listen_event(self._cb_current_changed, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _check_current_and_set_switch(self, current: float | None) -> None:
        """Check if current is above the threshold and set switch.

        Args:
            current: current value which should be checked
        """
        if current is None:
            return

        current_above_threshold = current > self._config.parameter.threshold

        if self._config.parameter.extended_time:
            if current_above_threshold:
                self._extended_countdown.stop()
                habapp_rules.core.helper.send_if_different(self._config.items.switch, "ON")

            elif not current_above_threshold and self._config.items.switch.is_on():
                # start or reset the countdown
                self._extended_countdown.reset()

        else:
            # extended time is not active
            habapp_rules.core.helper.send_if_different(self._config.items.switch, "ON" if current_above_threshold else "OFF")

    def _cb_current_changed(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if the current value changed.

        Args:
            event: event, which triggered this callback
        """
        self._check_current_and_set_switch(event.value)
