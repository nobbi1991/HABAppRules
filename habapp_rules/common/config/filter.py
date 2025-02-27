"""Config models for filter rules."""

import HABApp.openhab.items
import pydantic
import typing_extensions

import habapp_rules.core.pydantic_base


class ExponentialFilterItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for exponential filter."""

    raw: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="Item for raw value")
    filtered: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="Item for filtered value")


class ExponentialFilterParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for exponential filter."""

    tau: int = pydantic.Field(..., description="filter time constant in seconds. E.g. step from 0 to 1 | tau = 5 seconds -> after 5 seconds the value will be 0,67")
    instant_increase: bool = pydantic.Field(default=False, description="if set to True, increase of input values will not be filtered")
    instant_decrease: bool = pydantic.Field(default=False, description="if set to True, decrease of input values will not be filtered")

    @pydantic.model_validator(mode="after")
    def validate_instant_parameters(self) -> typing_extensions.Self:
        """Validate instant_increase and instant_decrease.

        Returns:
            validated model

        Raises:
            ValueError: if both parameters are set
        """
        if self.instant_decrease and self.instant_increase:
            msg = "instant_increase and instant_decrease can not be set to True at the same time!"
            raise ValueError(msg)
        return self


class ExponentialFilterConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for exponential filter."""

    items: ExponentialFilterItems = pydantic.Field(..., description="Items for exponential filter")
    parameter: ExponentialFilterParameter = pydantic.Field(..., description="Parameter for exponential filter")
