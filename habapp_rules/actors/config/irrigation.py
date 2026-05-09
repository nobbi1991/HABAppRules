"""Config models for irrigation rules."""

import pydantic
import typing_extensions
from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase


class IrrigationItems(ItemBase):
    """Items for irrigation rules."""

    valve: SwitchItem = pydantic.Field(..., description="valve item which will be switched")
    active: SwitchItem = pydantic.Field(..., description="item to activate the rule")
    hour: NumberItem = pydantic.Field(..., description="start hour")
    minute: NumberItem = pydantic.Field(..., description="start minute")
    duration: NumberItem = pydantic.Field(..., description="duration in minutes")
    repetitions: NumberItem | None = pydantic.Field(None, description="number of repetitions")
    brake: NumberItem | None = pydantic.Field(None, description="time in minutes between repetitions")

    @pydantic.model_validator(mode="after")
    def validate_model(self) -> typing_extensions.Self:
        """Validate model.

        Returns:
            validated model

        Raises:
            AssertionError: if 'repetitions' and 'brake' are not set together
        """
        if (self.repetitions is None) != (self.brake is None):
            msg = "If repeats item is given, also the brake item must be given!"
            raise AssertionError(msg)

        return self


class IrrigationConfig(ConfigBase):
    """Config for irrigation actors."""

    items: IrrigationItems = pydantic.Field(..., description="items for irrigation rule")
    parameter: None = None
