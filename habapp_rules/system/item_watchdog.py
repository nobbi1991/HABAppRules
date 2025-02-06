"""Watchdog rules."""

import HABApp

import habapp_rules.core.helper
from habapp_rules.system.config.item_watchdog import WatchdogConfig


class ItemWatchdog(HABApp.Rule):
    """Watchdog rule to check if the observed item was updated in time.

    # Items:
    Switch    Item_To_Observe   "Item which should be observed"
    Switch    Warning           "Warning, item was not updated in time"

    # Config:
    config = habapp_rules.system.config.WatchdogConfig(
            items=habapp_rules.system.config.WatchdogItems(
                    observed="Item_To_Observe",
                    warning="Warning")
    )

    # Rule init:
    habapp_rules.system.watchdog.Watchdog(config)
    """

    def __init__(self, config: WatchdogConfig) -> None:
        """Init watchdog rule.

        Args:
            config: Config for watchdog rule
        """
        HABApp.Rule.__init__(self)
        self._config = config

        self._countdown = self.run.countdown(self._config.parameter.timeout, habapp_rules.core.helper.send_if_different, item=self._config.items.warning, value="ON")
        self._countdown.reset()
        self._config.items.observed.listen_event(self._cb_observed_state_updated, HABApp.openhab.events.ItemStateUpdatedEventFilter())

    def _cb_observed_state_updated(self, event: HABApp.openhab.events.ItemStateUpdatedEvent) -> None:  # noqa: ARG002
        """Callback which is called if the observed item was updated.

        Args:
            event: event which triggered this callback
        """
        habapp_rules.core.helper.send_if_different(self._config.items.warning, "OFF")
        self._countdown.reset()
