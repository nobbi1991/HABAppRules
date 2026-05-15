"""Config rules for DWD rules."""

import logging

import pydantic
import typing_extensions
from HABApp.openhab.items import NumberItem, StringItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase

LOGGER = logging.getLogger(__name__)


class WindAlarmItems(ItemBase):
    """Items for DWD wind alarm rule."""

    wind_alarm: SwitchItem = pydantic.Field(..., description="item for wind alarm, which will be set to ON if wind alarm is active")
    manual: SwitchItem = pydantic.Field(..., description="switch item to disable all automatic functions")
    hand_timeout: NumberItem | None = pydantic.Field(default=None, description="item to set the hand timeout")
    state: StringItem = pydantic.Field(..., description="item for storing the current state")


class WindAlarmParameter(ParameterBase):
    """Parameter for DWD wind alarm rule."""

    hand_timeout: int | None = pydantic.Field(default=None, description="hand timeout in seconds or 0 for no timeout")
    dwd_item_prefix: str = pydantic.Field(default="I26_99_warning_", description="prefix of dwd warning names")
    number_dwd_objects: int = pydantic.Field(default=3, description="number of dwd objects")
    threshold_wind_speed: int = pydantic.Field(default=70, description="threshold for wind speed -> wind alarm will only be active if greater or equal")
    threshold_severity: int = pydantic.Field(default=2, description="threshold for severity -> wind alarm will only be active if greater or equal")


class WindAlarmConfig(ConfigBase):
    """Config for DWD wind alarm rule."""

    items: WindAlarmItems = pydantic.Field(..., description="items for DWD wind alarm rule")
    parameter: WindAlarmParameter = pydantic.Field(default=WindAlarmParameter(), description="parameters for DWD wind alarm rule")

    @pydantic.model_validator(mode="after")
    def check_hand_timeout(self) -> typing_extensions.Self:
        """Validate hand timeout.

        Returns:
            validated config model

        Raises:
            ValueError: if both 'items.hand_timeout' and 'parameter.hand_timeout' are set
        """
        if (self.items.hand_timeout is None) == (self.parameter.hand_timeout is None):
            msg = "Either 'items.wind_alarm' or 'parameter.hand_timeout' must be set"
            raise ValueError(msg)
        return self

    @property
    def hand_timeout(self) -> int:
        """Get value of hand timeout.

        Returns:
            hand timeout in seconds (0 is no timeout)

        Raises:
            HabAppRulesConfigurationError: if hand timeout is not configured
        """
        if self.items.hand_timeout is not None:
            if (item_value := self.items.hand_timeout.value) is None:
                LOGGER.warning("The value of the hand timeout item is None. Will use 24 hours as default!")
                return 24 * 3600
            return int(item_value)

        return self.parameter.hand_timeout  # type: ignore[return-value]  # check_hand_timeout ensures that either item or parameter is set
