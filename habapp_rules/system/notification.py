"""Rules for notification."""
import HABApp
from multi_notifier.connectors.connector_mail import Mail
from multi_notifier.connectors.connector_telegram import Telegram


class SendStateChanged(HABApp.Rule):
	"""Rule class to send a telegram if the state of an item changes."""

	def __init__(self, item_name: str, connector: Mail | Telegram, recipients: str | list[str]) -> None:
		"""Init the rule object.

		:param item_name: name of OpenHab item which should be monitored
		:param connector: connector which should be used
		:param recipients: recipients which should be notified
		"""
		self._recipients = recipients
		self._connector = connector

		HABApp.Rule.__init__(self)

		item = HABApp.openhab.items.OpenhabItem.get_item(item_name)
		item.listen_event(self._send_state_change, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _send_state_change(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is called if the state of the item changed.

		:param event: event which triggered the callback
		"""
		msg = f"{event.name} changed from {event.old_value} to {event.value}"

		if isinstance(self._connector, Telegram):
			self._connector.send_message(self._recipients, msg)
		else:
			self._connector.send_message(self._recipients, msg, subject=f"{event.name} changed")
