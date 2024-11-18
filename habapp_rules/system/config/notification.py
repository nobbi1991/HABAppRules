"""Config models for presence rules."""

import HABApp
import pydantic
from multi_notifier.connectors.connector_mail import Mail
from multi_notifier.connectors.connector_telegram import Telegram

import habapp_rules.core.pydantic_base


class NotificationItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for presence detection."""

    target_item: HABApp.openhab.items.OpenhabItem = pydantic.Field(..., description="Item which state change triggers a notification")


class NotificationParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for notification."""

    notify_connector: Mail | Telegram = pydantic.Field(..., description="Notifier which is used for sending notifications")
    recipients: str | list[str] = pydantic.Field(..., description="Recipients which should be notified")


class NotificationConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for notification."""

    items: NotificationItems = pydantic.Field(..., description="items for notification")
    parameter: NotificationParameter = pydantic.Field(..., description="parameter for notification")
