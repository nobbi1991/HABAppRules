"""Config models for HCL color rules."""

import operator

import pydantic
import typing_extensions
from HABApp.openhab.items import DimmerItem, NumberItem, StringItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class HclTimeItems(ItemBase):
    """Items for HCL color which depends on time."""

    color: NumberItem = pydantic.Field(..., description="HCL color which will be set by the HCL rule")
    manual: SwitchItem = pydantic.Field(..., description="switch item to disable all automatic functions")
    sleep_state: StringItem | None = pydantic.Field(default=None, description="sleep state item")
    focus: SwitchItem | None = pydantic.Field(default=None, description="focus state item")
    switch_on: SwitchItem | DimmerItem | None = pydantic.Field(default=None, description="switch item which triggers a color update if switched on")
    state: StringItem = pydantic.Field(..., description="state item for storing the current state")


class HclElevationItems(HclTimeItems):
    """Items for HCL color which depends on sun elevation."""

    elevation: NumberItem = pydantic.Field(..., description="sun elevation")


class HclElevationParameter(ParameterBase):
    """Parameter for HCL color."""

    color_map: list[tuple[int, int]] = pydantic.Field(default=[(-15, 3900), (0, 4500), (5, 5500), (15, 6500)], description="Color mapping. The first value is the sun elevation, the second is the HCL color")
    hand_timeout: int = pydantic.Field(default=18_000, description="hand timeout. After this time the HCL light rule will fall back to auto mode", gt=0)  # 5 hours
    sleep_color: float = pydantic.Field(default=2500, description="color if sleeping is active", gt=0)
    post_sleep_timeout: int = pydantic.Field(default=1, description="time after sleeping was active where the sleeping color will be set", gt=0)
    focus_color: float = pydantic.Field(default=6000, description="color if focus is active", gt=0)
    color_tolerance: int = pydantic.Field(default=10, description="color tolerance for hand detection", gt=0)

    @pydantic.model_validator(mode="after")
    def validate_model(self) -> typing_extensions.Self:
        """Sort color map.

        Returns:
             model with sorted color map
        """
        self.color_map = sorted(self.color_map, key=operator.itemgetter(0))
        return self


_DEFAULT_TIME_MAP = [(0, 2200), (4, 2200), (5, 3200), (6, 3940), (8, 5000), (12, 7000), (19, 7000), (21, 5450), (22, 4000), (23, 2600)]


class HclTimeParameter(HclElevationParameter):
    """Parameter for HCL color which depends on time."""

    color_map: list[tuple[int, int]] = pydantic.Field(default=_DEFAULT_TIME_MAP, description="Color mapping. The first value is the hour, the second is the HCL color")
    shift_weekend_holiday: bool = pydantic.Field(default=False, description="If this is active the color will shift on weekends and holidays for one hour")


class HclElevationConfig(ConfigBase):
    """Config for HCL color which depends on sun elevation."""

    items: HclElevationItems = pydantic.Field(..., description="items for HCL color which depends on sun elevation")
    parameter: HclElevationParameter = pydantic.Field(default=HclElevationParameter(), description="parameter for HCL color which depends on sun elevation")


class HclTimeConfig(ConfigBase):
    """Config for HCL color which depends on time."""

    items: HclTimeItems = pydantic.Field(..., description="items for HCL color which depends on time")
    parameter: HclTimeParameter = pydantic.Field(default=HclTimeParameter(), description="parameter for HCL color which depends on time")
