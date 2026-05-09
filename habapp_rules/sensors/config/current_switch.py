"""Config models for current switch rules."""

import pydantic
from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class CurrentSwitchItems(ItemBase):
    """Items for current switch the rule."""

    current: NumberItem = pydantic.Field(..., description="item which measures the current")
    switch: SwitchItem = pydantic.Field(..., description="item which should be switched on, if the current is above")


class CurrentSwitchParameter(ParameterBase):
    """Parameter for current switch the rules."""

    threshold: float = pydantic.Field(default=0.2, description="threshold for switching on")
    extended_time: float = pydantic.Field(default=0, description="extended time in seconds, if current is below threshold")


class CurrentSwitchConfig(ConfigBase):
    """Config models for current switch the rule."""

    items: CurrentSwitchItems = pydantic.Field(..., description="items for current switch rules")
    parameter: CurrentSwitchParameter = pydantic.Field(CurrentSwitchParameter(), description="parameter for current switch rules")
