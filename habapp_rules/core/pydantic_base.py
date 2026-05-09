"""Base classes for pydantic config models."""

import types
import typing
from typing import TypeVar

import pydantic
from HABApp.openhab.items import OpenhabItem, Thing

from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.core.helper import OH_ITEM_TYPE, create_additional_item


class BaseModel(pydantic.BaseModel):
    """Base class for pydantic models."""

    def __init__(self, **data: typing.Any) -> None:  # noqa: ANN401
        """Initialize the model.

        Args:
            data: data object given by pydantic

        Raises:
            HabAppRulesConfigurationError: if validation fails
        """
        try:
            super().__init__(**data)
        except pydantic.ValidationError as exc:
            msg = f"Failed to validate model: {exc.errors()}"
            raise HabAppRulesConfigurationError(msg) from exc


class ItemBase(BaseModel):
    """Base class for item config."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    @pydantic.model_validator(mode="before")
    @classmethod
    def check_all_fields_oh_items(cls, data: typing.Any) -> typing.Any:  # noqa: ANN401, C901
        """Validate that all fields are OpenHAB items.

        All items must be subclasses of `OpenhabItem` or `Thing`.
        If create_if_not_exists is set, only one type is allowed.
        For lists, only one type is allowed.

        Args:
            data: data object given by pydantic

        Returns:
            data object

        Raises:
            HabAppRulesConfigurationError: if validation fails
        """
        for name, field_info in cls.model_fields.items():
            field_types = cls._get_type_of_field(name)
            extra = field_info.json_schema_extra
            if callable(extra):
                # extra can be a callable in pydantic v2
                msg = "Callable not supported for json_schema_extra"
                raise HabAppRulesConfigurationError(msg)
            extra_args = extra or {}

            if isinstance(field_types, typing.TypeVar) and field_types.__bound__ is not None:
                field_types = field_types.__bound__
                if isinstance(field_types, types.UnionType):
                    field_types = [arg for arg in typing.get_args(field_types) if arg is not types.NoneType]

            if isinstance(field_types, types.GenericAlias):
                # type is list of OpenHAB items
                field_types = typing.get_args(field_types)[0]

                if isinstance(field_types, typing.TypeVar) and field_types.__bound__ is not None:
                    field_types = field_types.__bound__

                if isinstance(field_types, types.UnionType):
                    field_types = [arg for arg in typing.get_args(field_types) if arg is not types.NoneType]

                # validate that create_if_not_exists is not set for lists
                if extra_args.get("create_if_not_exists", False):
                    msg = "create_if_not_exists is not allowed for list fields"
                    raise HabAppRulesConfigurationError(msg)

            field_types = field_types if isinstance(field_types, list) else [field_types]

            for field_type in field_types:
                if not issubclass(field_type, OpenhabItem | Thing):
                    msg = f"Field {field_type} is not an OpenhabItem"
                    raise HabAppRulesConfigurationError(msg)

            # validate that only one type is given if create_if_not_exists is set
            if extra_args.get("create_if_not_exists", False) and len(field_types) > 1:
                msg = "If create_if_not_exists is set, only one type is allowed"
                raise HabAppRulesConfigurationError(msg)

        return data

    @pydantic.field_validator("*", mode="before")
    @classmethod
    def convert_to_oh_item(cls, var: str | OpenhabItem, validation_info: pydantic.ValidationInfo) -> OpenhabItem | Thing | list[OpenhabItem | Thing] | None:
        """Convert to OpenHAB item.

        Args:
            var: variable given by the user
            validation_info: validation info given by pydantic

        Returns:
            variable converted to OpenHAB item

        Raises:
            HabAppRulesConfigurationError: if type is not supported
        """
        if (field_name := validation_info.field_name) is None:
            msg = "Field name is required"  # pragma: no cover # very unrealistic
            raise HabAppRulesConfigurationError(msg)  # pragma: no cover # very unrealistic

        extra = cls.model_fields[field_name].json_schema_extra
        extra_args = extra or {}
        create_if_not_exists = extra_args.get("create_if_not_exists", False)  # type: ignore[union-attr]  # ensured by check_all_fields_oh_items

        if create_if_not_exists and isinstance(var, str):
            item_class = cls._get_type_of_field(field_name)
            return create_additional_item(var, item_class)  # type: ignore[arg-type]  # ensured by check_all_fields_oh_items

        if isinstance(var, list):
            return [cls._get_oh_item(itm) for itm in var]

        if issubclass(type(var), OpenhabItem) or isinstance(var, str):
            return cls._get_oh_item(var)

        if var is None:
            return None

        msg = f"The following var is not supported: {var}"
        raise HabAppRulesConfigurationError(msg)

    @staticmethod
    def _get_oh_item(item: str | OpenhabItem) -> OpenhabItem | Thing:
        """Get OpenHAB item from string or OpenHAB item.

        Args:
            item: name of OpenHAB item or OpenHAB item

        Returns:
            OpenHAB item

        Raises:
            HabAppRulesConfigurationError: if type is not supported
        """
        if isinstance(item, str):
            if ":" in item:
                return Thing.get_item(item)
            return OpenhabItem.get_item(item)

        return item

    @classmethod
    def _get_type_of_field(cls, field_name: str) -> type[OH_ITEM_TYPE] | list[type[OH_ITEM_TYPE]]:
        """Get type of field.

        Args:
            field_name: name of field

        Returns:
            type of field, NoneType will be ignored

        Raises:
            HabAppRulesConfigurationError: if field type is not set
        """
        field_type = cls.model_fields[field_name].annotation
        if field_type is None:
            msg = "field type not set"  # pragma: no cover  # should be covered by pydantic validator
            raise HabAppRulesConfigurationError(msg)  # pragma: no cover  # should be covered by pydantic validator

        if isinstance(field_type, types.UnionType):
            field_type = [arg for arg in typing.get_args(field_type) if arg is not types.NoneType]
        return field_type


class ParameterBase(BaseModel):
    """Base class for parameter config."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)


ITEM = TypeVar("ITEM", bound=ItemBase)
PARAM = TypeVar("PARAM", bound=ParameterBase)


class ConfigBase(BaseModel, typing.Generic[ITEM, PARAM]):
    """Base class for config objects."""

    items: ITEM | None
    parameter: PARAM | None
