"""Config models for sleep rules."""

import datetime

import pydantic
from HABApp.openhab.items import StringItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class SleepItems(ItemBase):
    """Items for sleep detection."""

    sleep: SwitchItem = pydantic.Field(..., description="sleep item")
    sleep_request: SwitchItem = pydantic.Field(..., description="sleep request item")
    lock: SwitchItem | None = pydantic.Field(None, description="lock item")
    lock_request: SwitchItem | None = pydantic.Field(None, description="lock request item")
    display_text: StringItem | None = pydantic.Field(None, description="display text item")
    state: StringItem = pydantic.Field(..., description="state item")


class SleepConfig(ConfigBase):
    """Config for sleep detection."""

    items: SleepItems = pydantic.Field(..., description="items for sleep state")
    parameter: None = None


# LINK SLEEP ##############################


class LinkSleepItems(ItemBase):
    """Items for sleep detection."""

    sleep_master: SwitchItem = pydantic.Field(..., description="sleep item of the the master item which will link it's state to the slave items")
    sleep_request_slaves: list[SwitchItem] = pydantic.Field(..., description="list of sleep request items of the slaves")
    link_active_feedback: SwitchItem | None = pydantic.Field(None, description="item which is ON if link is active or OFF if link is not active anymore")


class LinkSleepParameter(ParameterBase):
    """Config for sleep detection."""

    link_time_start: datetime.time = pydantic.Field(default=datetime.time(0), description="Start time when the linking is active")
    link_time_end: datetime.time = pydantic.Field(default=datetime.time(23, 59, 59), description="End time when the linking is not active anymore")


class LinkSleepConfig(ConfigBase):
    """Config for sleep detection."""

    items: LinkSleepItems = pydantic.Field(..., description="items for sleep state")
    parameter: LinkSleepParameter = pydantic.Field(LinkSleepParameter(), description="parameter for link sleep")
