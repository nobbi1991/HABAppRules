"""Config models for heating rules."""

import datetime

import pydantic
from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class KnxHeatingItems(ItemBase):
    """Items for KNX heating abstraction rule."""

    virtual_temperature: NumberItem = pydantic.Field(..., description="temperature item, which is used in OpenHAB to set the target temperature")
    actor_feedback_temperature: NumberItem = pydantic.Field(..., description="temperature item, which holds the current target temperature set by the heating actor")
    temperature_offset: NumberItem = pydantic.Field(..., description="item for setting the offset temperature")


class KnxHeatingConfig(ConfigBase):
    """Config for KNX heating abstraction rule."""

    items: KnxHeatingItems = pydantic.Field(..., description="items for heating rule")
    parameter: None = None


class HeatingActiveItems(ItemBase):
    """Items for active heating rule."""

    control_values: list[NumberItem] = pydantic.Field(..., description="list of control value items")
    output: SwitchItem = pydantic.Field(..., description="output item, which is ON when at least one control value is above the threshold")


class HeatingActiveParameter(ParameterBase):
    """Parameters for active heating rule."""

    threshold: float = pydantic.Field(default=0, description="control value threshold")
    extended_active_time: datetime.timedelta = pydantic.Field(default=datetime.timedelta(days=1), description="extended time to keep the output item ON, after last control value change below the threshold")


class HeatingActiveConfig(ConfigBase):
    """Config for active heating rule."""

    items: HeatingActiveItems = pydantic.Field(..., description="items for active heating rule")
    parameter: HeatingActiveParameter = pydantic.Field(default=HeatingActiveParameter(), description="parameters for active heating rule")
