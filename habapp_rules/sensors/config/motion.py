"""Config models for motion rules."""

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class MotionItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for motion."""

    motion_raw: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="unfiltered motion item")
    motion_filtered: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="filtered motion item")
    brightness: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="brightness item")
    brightness_threshold: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="brightness threshold item")
    lock: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="lock item")
    sleep_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sleep state item")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="state item")


class MotionParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for motion."""

    extended_motion_time: int = pydantic.Field(5, description="extended motion time in seconds")
    brightness_threshold: float | None = pydantic.Field(None, description="brightness threshold value")
    post_sleep_lock_time: int = pydantic.Field(10, description="post sleep lock time in seconds")


class MotionConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for motion."""

    items: MotionItems = pydantic.Field(..., description="items for motion")
    parameter: MotionParameter = pydantic.Field(MotionParameter(), description="parameter for motion")
