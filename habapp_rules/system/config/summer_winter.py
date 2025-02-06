"""Config models for summer / winter rules."""

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class SummerWinterItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for summer/winter detection."""

    outside_temperature: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="outside temperature item")
    summer: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="summer item")
    last_check: HABApp.openhab.items.DatetimeItem | None = pydantic.Field(None, description="last check item")


class SummerWinterParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for summer/winter detection."""

    persistence_service: str | None = pydantic.Field(None, description="name of persistence service")
    days: int = pydantic.Field(5, description="number of days in the past which will be used to check if it is summer")
    temperature_threshold: float = pydantic.Field(16, description="threshold weighted temperature for summer")


class SummerWinterConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for summer/winter detection."""

    items: SummerWinterItems = pydantic.Field(..., description="items for summer/winter state")
    parameter: SummerWinterParameter = pydantic.Field(SummerWinterParameter(), description="parameter for summer/winter")
