"""Config models for energy_save_switch rules."""

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class EnergySaveSwitchItems(habapp_rules.core.pydantic_base.ItemBase):
    """Item config for EnergySaveSwitch rule."""

    switch: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="switch item, which will be handled")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item to store the current state of the state machine")
    manual: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="item to switch to manual mode and disable the automatic functions")
    presence_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="presence state set via habapp_rules.presence.Presence")
    sleeping_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sleeping state set via habapp_rules.system.sleep.Sleep")
    external_request: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="item to request ON state from external. This request will overwrite the target state of presence / sleeping.")
    current: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="item which measures the current")


class EnergySaveSwitchParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter config for EnergySaveSwitch rule."""

    max_on_time: int | None = pydantic.Field(None, description="maximum on time in seconds. None means no timeout. If the external request item is ON, the timeout will be extended till the external request is OFF.")
    hand_timeout: int | None = pydantic.Field(None, description="Fallback time from hand to automatic mode in seconds. None means no timeout.")
    current_threshold: float = pydantic.Field(0.030, description="threshold in Ampere.")
    extended_wait_for_current_time: int = pydantic.Field(60, description="Extended time to wait time before switch off the relay in seconds. If current goes above threshold, it will jump back to ON state.", gt=0)


class EnergySaveSwitchConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for EnergySaveSwitch rule."""

    items: EnergySaveSwitchItems = pydantic.Field(..., description="Config items for power switch rule")
    parameter: EnergySaveSwitchParameter = pydantic.Field(EnergySaveSwitchParameter(), description="Config parameter for power switch rule")
