"""Config models for presence rules."""

import pydantic
from HABApp.openhab.items import OpenhabItem
from multi_notifier.connectors.connector_mail import Mail
from multi_notifier.connectors.connector_telegram import Telegram

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class NotificationItems(ItemBase):
    """Items for presence detection."""

    target_item: OpenhabItem = pydantic.Field(..., description="Item which state change triggers a notification")


class NotificationParameter(ParameterBase):
    """Parameter for notification."""

    notify_connector: Mail | Telegram = pydantic.Field(..., description="Notifier which is used for sending notifications")
    recipients: str | list[str] = pydantic.Field(..., description="Recipients which should be notified")


class NotificationConfig(ConfigBase):
    """Config for notification."""

    items: NotificationItems = pydantic.Field(..., description="items for notification")
    parameter: NotificationParameter = pydantic.Field(..., description="parameter for notification")
