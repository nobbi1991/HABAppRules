"""Config models for logic rules."""

import typing

import pydantic
import typing_extensions
from HABApp.openhab.items import ContactItem, DimmerItem, NumberItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase

_LOGIC_ITEM_TYPE = typing.TypeVar("_LOGIC_ITEM_TYPE", bound=SwitchItem | ContactItem | NumberItem | DimmerItem)
_BINARY_ITEM_TYPE = typing.TypeVar("_BINARY_ITEM_TYPE", bound=SwitchItem | ContactItem)
_NUMERIC_ITEM_TYPE = typing.TypeVar("_NUMERIC_ITEM_TYPE", bound=NumberItem | DimmerItem)


class _LogicItemsBase(ItemBase, typing.Generic[_LOGIC_ITEM_TYPE]):
    """Base class for logic items."""

    inputs: list[_LOGIC_ITEM_TYPE] = pydantic.Field(..., description="List of input items (must be either Switch or Contact and all have to match to output_item)")
    output: _LOGIC_ITEM_TYPE = pydantic.Field(..., description="Output item")

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


class BinaryLogicItems(_LogicItemsBase[_BINARY_ITEM_TYPE], typing.Generic[_BINARY_ITEM_TYPE]):
    """Items for binary logic."""

    inputs: list[_BINARY_ITEM_TYPE] = pydantic.Field(..., description="List of input items (must be either Switch or Contact and all have to match to output_item)")
    output: _BINARY_ITEM_TYPE = pydantic.Field(..., description="Output item")


class BinaryLogicConfig(ConfigBase):
    """Config for binary logic."""

    items: BinaryLogicItems = pydantic.Field(..., description="Items for binary logic")
    parameter: None = None


class NumericLogicItems(_LogicItemsBase[_NUMERIC_ITEM_TYPE], typing.Generic[_NUMERIC_ITEM_TYPE]):
    """Items for numeric logic."""

    inputs: list[_NUMERIC_ITEM_TYPE] = pydantic.Field(..., description="List of input items (must be either Number or Dimmer and all have to match to output_item)")
    output: _NUMERIC_ITEM_TYPE = pydantic.Field(..., description="Output item")


class NumericLogicParameter(ParameterBase):
    """Parameter for numeric logic."""

    ignore_old_values_time: int | None = pydantic.Field(default=None, description="ignores values which are older than the given time in seconds. If None, all values will be taken")


class NumericLogicConfig(ConfigBase):
    """Config for numeric logic."""

    items: NumericLogicItems = pydantic.Field(..., description="Items for numeric logic")
    parameter: NumericLogicParameter = pydantic.Field(NumericLogicParameter(), description="Parameter for numeric logic")


class InvertValueItems(ItemBase):
    """Items for invert value."""

    input: NumberItem = pydantic.Field(..., description="Input item")
    output: NumberItem = pydantic.Field(..., description="Output item")


class InvertValueParameter(ParameterBase):
    """Parameter for invert value."""

    only_positive: bool = pydantic.Field(default=False, description="if true, only positive values will be set to output item")
    only_negative: bool = pydantic.Field(default=False, description="if true, only negative values will be set to output item")


class InvertValueConfig(ConfigBase):
    """Config for invert value."""

    items: InvertValueItems = pydantic.Field(..., description="Items for invert value")
    parameter: InvertValueParameter = pydantic.Field(InvertValueParameter(), description="Parameter for invert value")
