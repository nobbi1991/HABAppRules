"""Config models for sleep rules."""

import datetime

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class SleepItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for sleep detection."""

    sleep: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="sleep item")
    sleep_request: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="sleep request item")
    lock: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="lock item")
    lock_request: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="lock request item")
    display_text: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="display text item")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="state item")


class SleepConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for sleep detection."""

    items: SleepItems = pydantic.Field(..., description="items for sleep state")
    parameter: None = None


# LINK SLEEP ##############################


class LinkSleepItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for sleep detection."""

    sleep_master: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="sleep item of the the master item which will link it's state to the slave items")
    sleep_request_slaves: list[HABApp.openhab.items.SwitchItem] = pydantic.Field(..., description="list of sleep request items of the slaves")
    link_active_feedback: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="item which is ON if link is active or OFF if link is not active anymore")


class LinkSleepParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Config for sleep detection."""

    link_time_start: datetime.time = pydantic.Field(datetime.time(0), description="Start time when the linking is active")
    link_time_end: datetime.time = pydantic.Field(datetime.time(23, 59, 59), description="End time when the linking is not active anymore")


class LinkSleepConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for sleep detection."""

    items: LinkSleepItems = pydantic.Field(..., description="items for sleep state")
    parameter: LinkSleepParameter = pydantic.Field(LinkSleepParameter(), description="parameter for link sleep")
