"""Config rules for DWD rules."""

import HABApp
import pydantic
import typing_extensions

import habapp_rules.core.pydantic_base


class WindAlarmItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for DWD wind alarm rule."""

    wind_alarm: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item for wind alarm, which will be set to ON if wind alarm is active")
    manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="switch item to disable all automatic functions")
    hand_timeout: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="item to set the hand timeout")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item for storing the current state")


class WindAlarmParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for DWD wind alarm rule."""

    hand_timeout: int | None = pydantic.Field(None, description="hand timeout in seconds or 0 for no timeout")
    dwd_item_prefix: str = pydantic.Field("I26_99_warning_", description="prefix of dwd warning names")
    number_dwd_objects: int = pydantic.Field(3, description="number of dwd objects")
    threshold_wind_speed: int = pydantic.Field(70, description="threshold for wind speed -> wind alarm will only be active if greater or equal")
    threshold_severity: int = pydantic.Field(2, description="threshold for severity -> wind alarm will only be active if greater or equal")


class WindAlarmConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for DWD wind alarm rule."""

    items: WindAlarmItems = pydantic.Field(..., description="items for DWD wind alarm rule")
    parameter: WindAlarmParameter = pydantic.Field(WindAlarmParameter(), description="parameters for DWD wind alarm rule")

    @pydantic.model_validator(mode="after")
    def check_hand_timeout(self) -> typing_extensions.Self:
        """Validate hand timeout.

        Returns:
            validated config model

        Raises:
            ValueError: if both 'items.hand_timeout' and 'parameter.hand_timeout' are set
        """
        if not (self.items.hand_timeout is None) ^ (self.parameter.hand_timeout is None):  # XNOR
            msg = "Either 'items.wind_alarm' or 'parameter.hand_timeout' must be set"
            raise ValueError(msg)
        return self
