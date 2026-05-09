"""Config models for motion rules."""

import pydantic
import typing_extensions
from HABApp.openhab.items import NumberItem, StringItem, SwitchItem
from pydantic import model_validator

from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class MotionItems(ItemBase):
    """Items for motion."""

    motion_raw: SwitchItem = pydantic.Field(..., description="unfiltered motion item")
    motion_filtered: SwitchItem = pydantic.Field(..., description="filtered motion item")
    brightness: NumberItem | None = pydantic.Field(None, description="brightness item")
    brightness_threshold: NumberItem | None = pydantic.Field(None, description="brightness threshold item")
    lock: SwitchItem | None = pydantic.Field(None, description="lock item")
    sleep_state: StringItem | None = pydantic.Field(None, description="sleep state item")
    state: StringItem = pydantic.Field(..., description="state item")

    @model_validator(mode="after")
    def check_brightness_threshold(self) -> typing_extensions.Self:
        """Validate brightness threshold.

        Returns:
            validated model

        Raises:
            ValueError: if brightness threshold is not set ether by brightness_threshold item or parameter
        """
        if self.brightness_threshold is not None and self.brightness is None:
            msg = "Brightness threshold item is set but brightness item is not set"
            raise ValueError(msg)

        return self


class MotionParameter(ParameterBase):
    """Parameter for motion."""

    extended_motion_time: int = pydantic.Field(default=5, description="extended motion time in seconds")
    brightness_threshold: float | None = pydantic.Field(default=None, description="brightness threshold value")
    post_sleep_lock_time: int = pydantic.Field(default=10, description="post sleep lock time in seconds")


class MotionConfig(ConfigBase):
    """Config for motion."""

    items: MotionItems = pydantic.Field(..., description="items for motion")
    parameter: MotionParameter = pydantic.Field(MotionParameter(), description="parameter for motion")

    @model_validator(mode="after")
    def check_brightness_threshold(self) -> typing_extensions.Self:
        """Validate brightness threshold.

        Returns:
            validated model

        Raises:
            ValueError: if brightness threshold is not set ether by item or parameter
        """
        if self.items.brightness is not None:
            if self.items.brightness_threshold is None and self.parameter.brightness_threshold is None:
                msg = "brightness threshold must be set ether by item or parameter. None of them is set"
                raise ValueError(msg)

            if self.items.brightness_threshold is not None and self.parameter.brightness_threshold is not None:
                msg = "brightness threshold must be set ether by item or parameter. Both are set!"
                raise ValueError(msg)

        return self

    @property
    def brightness_threshold(self) -> float:
        """Get the current brightness threshold value.

        Returns:
            brightness threshold

        Raises:
            HabAppRulesConfigurationError: if brightness value not given by item or value
        """
        if self.parameter.brightness_threshold:
            return self.parameter.brightness_threshold
        if self.items.brightness_threshold is not None:
            return value if (value := self.items.brightness_threshold.value) else float("inf")

        msg = f"Can not get brightness threshold. Brightness value or item is not given. value: {self.parameter.brightness_threshold} | item: {self.items.brightness_threshold}"
        raise HabAppRulesConfigurationError(msg)
