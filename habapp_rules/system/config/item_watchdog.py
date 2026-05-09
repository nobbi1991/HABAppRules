"""Config models for watchdog rules."""

import pydantic
from HABApp.openhab.items import OpenhabItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class WatchdogItems(ItemBase):
    """Items for watchdog rule."""

    observed: OpenhabItem = pydantic.Field(..., description="observed item")
    warning: SwitchItem = pydantic.Field(..., description="warning item, which will be set to ON if the observed item was not updated in the expected time")


class WatchdogParameter(ParameterBase):
    """Parameter for watchdog rule."""

    timeout: int = pydantic.Field(default=3600, description="timeout in seconds")


class WatchdogConfig(ConfigBase):
    """Config for watchdog rule."""

    items: WatchdogItems = pydantic.Field(..., description="items for watchdog rule")
    parameter: WatchdogParameter = pydantic.Field(WatchdogParameter(), description="parameters for watchdog rule")
