"""Config models for watchdog rules."""

import HABApp.openhab.items
import pydantic

import habapp_rules.core.pydantic_base


class WatchdogItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for watchdog rule."""

    observed: HABApp.openhab.items.OpenhabItem = pydantic.Field(..., description="observed item")
    warning: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="warning item, which will be set to ON if the observed item was not updated in the expected time")


class WatchdogParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for watchdog rule."""

    timeout: int = pydantic.Field(3600, description="timeout in seconds")


class WatchdogConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for watchdog rule."""

    items: WatchdogItems = pydantic.Field(..., description="items for watchdog rule")
    parameter: WatchdogParameter = pydantic.Field(WatchdogParameter(), description="parameters for watchdog rule")
