"""Watchdog rules."""

from HABApp.openhab.events import ItemStateUpdatedEvent, ItemStateUpdatedEventFilter

from habapp_rules.core.base import RuleBase
from habapp_rules.core.helper import send_if_different
from habapp_rules.system.config.item_watchdog import WatchdogConfig


class ItemWatchdog(RuleBase):
    """Watchdog rule to check if the observed item was updated in time.

    # Items:
    Switch    Item_To_Observe   "Item which should be observed"
    Switch    Warning           "Warning, item was not updated in time"

    # Config:
    config = WatchdogConfig(
            items=WatchdogItems(
                    observed="Item_To_Observe",
                    warning="Warning")
    )

    # Rule init:
    Watchdog(config)
    """

    def __init__(self, config: WatchdogConfig) -> None:
        """Init watchdog rule.

        Args:
            config: Config for watchdog rule
        """
        RuleBase.__init__(self, config.items.observed.name)
        self._config = config

        self._countdown = self.run.countdown(self._config.parameter.timeout, send_if_different, item=self._config.items.warning, value="ON")
        self._countdown.reset()
        self._config.items.observed.listen_event(self._cb_observed_state_updated, ItemStateUpdatedEventFilter())
        self._log_init_done()

    def _cb_observed_state_updated(self, _: ItemStateUpdatedEvent) -> None:
        """Callback which is called if the observed item was updated."""
        send_if_different(self._config.items.warning, "OFF")
        self._countdown.reset()
