"""Config models for presence rules."""

import pydantic
from HABApp.openhab.items import ContactItem, StringItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase


class PresenceItems(ItemBase):
    """Items for presence detection."""

    presence: SwitchItem = pydantic.Field(..., description="presence item")
    leaving: SwitchItem = pydantic.Field(..., description="leaving item")
    outdoor_doors: list[ContactItem] = pydantic.Field(default=[], description="list of door contacts which are used to detect presence if outside door was opened")
    phones: list[SwitchItem] = pydantic.Field(default=[], description="list of phone items which are used to detect presence and leaving depending on present phones")
    state: StringItem = pydantic.Field(..., description="state item")


class PresenceConfig(ConfigBase):
    """Config for presence detection."""

    items: PresenceItems = pydantic.Field(..., description="items for presence detection")
    parameter: None = None
