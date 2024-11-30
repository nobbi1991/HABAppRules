"""Config models for heating rules."""

import datetime

import HABApp.openhab.items
import pydantic

import habapp_rules.core.pydantic_base


class KnxHeatingItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for KNX heating abstraction rule."""

    virtual_temperature: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="temperature item, which is used in OpenHAB to set the target temperature")
    actor_feedback_temperature: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="temperature item, which holds the current target temperature set by the heating actor")
    temperature_offset: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="item for setting the offset temperature")


class KnxHeatingConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for KNX heating abstraction rule."""

    items: KnxHeatingItems = pydantic.Field(..., description="items for heating rule")
    parameter: None = None


class HeatingActiveItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for active heating rule."""

    control_values: list[HABApp.openhab.items.NumberItem] = pydantic.Field(..., description="list of control value items")
    output: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="output item, which is ON when at least one control value is above the threshold")


class HeatingActiveParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameters for active heating rule."""

    threshold: float = pydantic.Field(0, description="control value threshold")
    extended_active_time: datetime.timedelta = pydantic.Field(datetime.timedelta(days=1), description="extended time to keep the output item ON, after last control value change below the threshold")


class HeatingActiveConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for active heating rule."""

    items: HeatingActiveItems = pydantic.Field(..., description="items for active heating rule")
    parameter: HeatingActiveParameter = pydantic.Field(HeatingActiveParameter(), description="parameters for active heating rule")
