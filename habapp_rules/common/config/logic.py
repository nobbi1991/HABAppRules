"""Config models for logic rules."""

import HABApp
import pydantic
import typing_extensions

import habapp_rules.core.pydantic_base


class BinaryLogicItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for binary logic."""

    inputs: list[HABApp.openhab.items.SwitchItem | HABApp.openhab.items.ContactItem] = pydantic.Field(..., description="List of input items (must be either Switch or Contact and all have to match to output_item)")
    output: HABApp.openhab.items.SwitchItem | HABApp.openhab.items.ContactItem = pydantic.Field(..., description="Output item")

    @pydantic.model_validator(mode="after")
    def validate_items(self) -> typing_extensions.Self:
        """Validate if all items are of the same type.

        Returns:
            validated model

        Raises:
            TypeError: if not all items are of the same type
        """
        for item in self.inputs:
            if not isinstance(item, type(self.output)):
                msg = f"Item '{item.name}' must have the same type like the output item. Expected: {type(self.output)} | actual : {type(item)}"
                raise TypeError(msg)
        return self


class BinaryLogicConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for binary logic."""

    items: BinaryLogicItems = pydantic.Field(..., description="Items for binary logic")
    parameter: None = None


class NumericLogicItems(BinaryLogicItems):
    """Items for numeric logic."""

    inputs: list[HABApp.openhab.items.NumberItem | HABApp.openhab.items.DimmerItem] = pydantic.Field(..., description="List of input items (must be either Number or Dimmer and all have to match to output_item)")
    output: HABApp.openhab.items.NumberItem | HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="Output item")


class NumericLogicParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for numeric logic."""

    ignore_old_values_time: int | None = pydantic.Field(None, description="ignores values which are older than the given time in seconds. If None, all values will be taken")


class NumericLogicConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for numeric logic."""

    items: NumericLogicItems = pydantic.Field(..., description="Items for numeric logic")
    parameter: NumericLogicParameter = pydantic.Field(NumericLogicParameter(), description="Parameter for numeric logic")


class InvertValueItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for invert value."""

    input: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="Input item")
    output: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="Output item")


class InvertValueParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for invert value."""

    only_positive: bool = pydantic.Field(default=False, description="if true, only positive values will be set to output item")
    only_negative: bool = pydantic.Field(default=False, description="if true, only negative values will be set to output item")


class InvertValueConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for invert value."""

    items: InvertValueItems = pydantic.Field(..., description="Items for invert value")
    parameter: InvertValueParameter = pydantic.Field(InvertValueParameter(), description="Parameter for invert value")
