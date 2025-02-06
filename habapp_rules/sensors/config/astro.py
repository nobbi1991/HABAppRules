"""Config models for astro rules."""

import HABApp.openhab.items
import pydantic

import habapp_rules.core.pydantic_base


class _NightDayItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for night day."""

    elevation: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="Elevation of the sun")


class SetDayItems(_NightDayItems):
    """Items for setting day."""

    day: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="Item which should be set to ON after dawn and OFF after dusk")


class SetNightItems(_NightDayItems):
    """Items for setting night."""

    night: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="Item which should be set to ON after dusk and OFF after dawn")


class SetDayParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for setting day."""

    elevation_threshold: float = pydantic.Field(0.0, description="Threshold value for elevation. If the sun elevation is greater than the threshold, the day item will be set to ON")


class SetNightParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for setting night."""

    elevation_threshold: float = pydantic.Field(-8.0, description="Threshold value for elevation. If the sun elevation is greater than the threshold, the night item will be set to ON")


class SetDayConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for setting day."""

    items: SetDayItems = pydantic.Field(..., description="Items for setting day")
    parameter: SetDayParameter = pydantic.Field(SetDayParameter(), description="Parameter for setting day")


class SetNightConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for setting night."""

    items: SetNightItems = pydantic.Field(..., description="Items for setting night")
    parameter: SetNightParameter = pydantic.Field(SetNightParameter(), description="Parameter for setting night")
