"""Config models for irrigation rules."""

import HABApp.openhab.items
import pydantic
import typing_extensions

import habapp_rules.core.pydantic_base


class IrrigationItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for irrigation rules."""

    valve: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="valve item which will be switched")
    active: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item to activate the rule")
    hour: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="start hour")
    minute: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="start minute")
    duration: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="duration in minutes")
    repetitions: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="number of repetitions")
    brake: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="time in minutes between repetitions")

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


class IrrigationConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for irrigation actors."""

    items: IrrigationItems = pydantic.Field(..., description="items for irrigation rule")
    parameter: None = None
