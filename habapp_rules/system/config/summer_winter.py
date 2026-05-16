"""Config models for summer / winter rules."""

import pydantic
from HABApp.openhab.items import DatetimeItem, NumberItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class SummerWinterItems(ItemBase):
    """Items for summer/winter detection."""

    outside_temperature: NumberItem = pydantic.Field(..., description="outside temperature item")
    summer: SwitchItem = pydantic.Field(..., description="summer item")
    last_check: DatetimeItem | None = pydantic.Field(default=None, description="last check item")


class SummerWinterParameter(ParameterBase):
    """Parameter for summer/winter detection."""

    persistence_service: str | None = pydantic.Field(default=None, description="name of persistence service")
    days: int = pydantic.Field(default=5, description="number of days in the past which will be used to check if it is summer")
    temperature_threshold: float = pydantic.Field(default=16, description="threshold weighted temperature for summer")


class SummerWinterConfig(ConfigBase):
    """Config for summer/winter detection."""

    items: SummerWinterItems = pydantic.Field(..., description="items for summer/winter state")
    parameter: SummerWinterParameter = pydantic.Field(default=SummerWinterParameter(), description="parameter for summer/winter")
