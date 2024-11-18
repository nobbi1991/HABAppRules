"""Config models for presence rules."""

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class PresenceItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for presence detection."""

    presence: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="presence item")
    leaving: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="leaving item")
    outdoor_doors: list[HABApp.openhab.items.ContactItem] = pydantic.Field([], description="list of door contacts which are used to detect presence if outside door was opened")
    phones: list[HABApp.openhab.items.SwitchItem] = pydantic.Field([], description="list of phone items which are used to detect presence and leaving depending on present phones")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="state item")


class PresenceConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for presence detection."""

    items: PresenceItems = pydantic.Field(..., description="items for presence detection")
    parameter: None = None
