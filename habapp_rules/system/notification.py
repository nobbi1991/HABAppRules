"""Rules for notification."""

from HABApp.openhab.events import ItemStateChangedEvent, ItemStateChangedEventFilter
from multi_notifier.connectors.connector_telegram import Telegram

from habapp_rules.core.base import RuleBase
from habapp_rules.system.config.notification import NotificationConfig


class SendStateChanged(RuleBase):
    """Rule class to send a telegram if the state of an item changes."""

    def __init__(self, config: NotificationConfig) -> None:
        """Init the rule object.

        Args:
            config: config for notification rule
        """
        self._config = config
        RuleBase.__init__(self, config.items.target_item.name)

        self._config.items.target_item.listen_event(self._send_state_change, ItemStateChangedEventFilter())
        self._log_init_done()

    def _send_state_change(self, event: ItemStateChangedEvent) -> None:
        """Callback which is called if the state of the item changed.

        Args:
            event: event which triggered the callback
        """
        msg = f"{event.name} changed from {event.old_value} to {event.value}"

        if isinstance(self._config.parameter.notify_connector, Telegram):
            self._config.parameter.notify_connector.send_message(self._config.parameter.recipients, msg)
        else:
            self._config.parameter.notify_connector.send_message(self._config.parameter.recipients, msg, subject=f"{event.name} changed")
