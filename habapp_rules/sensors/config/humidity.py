"""Config models for humidity rules."""

import pydantic
from HABApp.openhab.items import NumberItem, StringItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class HumiditySwitchItems(ItemBase):
    """Items for humidity switch."""

    humidity: NumberItem = pydantic.Field(..., description="item which holds the measured humidity")
    output: SwitchItem = pydantic.Field(..., description="item which will be switched on if high humidity is detected")
    state: StringItem = pydantic.Field(..., description="item to store the state")


class HumiditySwitchParameter(ParameterBase):
    """Parameter for humidity switch."""

    absolute_threshold: float = pydantic.Field(default=65, description="threshold for high humidity")
    extended_time: int = pydantic.Field(default=10 * 60, description="extended time in seconds, if humidity is below threshold")


class HumiditySwitchConfig(ConfigBase):
    """Config for humidity switch."""

    items: HumiditySwitchItems = pydantic.Field(..., description="items for humidity switch")
    parameter: HumiditySwitchParameter = pydantic.Field(default=HumiditySwitchParameter(), description="parameter for humidity switch")
