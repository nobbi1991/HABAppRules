"""Config models for humidity rules."""

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class HumiditySwitchItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for humidity switch."""

    humidity: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="item which holds the measured humidity")
    output: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which will be switched on if high humidity is detected")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item to store the state")


class HumiditySwitchParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for humidity switch."""

    absolute_threshold: float = pydantic.Field(65, description="threshold for high humidity")
    extended_time: int = pydantic.Field(10 * 60, description="extended time in seconds, if humidity is below threshold")


class HumiditySwitchConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for humidity switch."""

    items: HumiditySwitchItems = pydantic.Field(..., description="items for humidity switch")
    parameter: HumiditySwitchParameter = pydantic.Field(HumiditySwitchParameter(), description="parameter for humidity switch")
