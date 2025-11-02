"""Base classes for pydantic config models."""

import types
import typing

import HABApp.openhab.items
import pydantic

import habapp_rules.core.exceptions
import habapp_rules.core.helper


class ItemBase(pydantic.BaseModel):
    """Base class for item config."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

    @pydantic.model_validator(mode="before")
    @classmethod
    def check_all_fields_oh_items(cls, data: typing.Any) -> typing.Any:  # noqa: ANN401
        """Validate that all fields are OpenHAB items.

        All items must be subclasses of `HABApp.openhab.items.OpenhabItem`.
        If create_if_not_exists is set, only one type is allowed.
        For lists, only one type is allowed.

        Args:
            data: data object given by pydantic

        Returns:
            data object

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationError: if validation fails
        """
        for name, field_info in cls.model_fields.items():
            field_types = cls._get_type_of_field(name)
            extra_args = extra if (extra := field_info.json_schema_extra) else {}

            if isinstance(field_types, types.GenericAlias):
                # type is list of OpenHAB items
                field_types = typing.get_args(field_types)[0]

                if isinstance(field_types, types.UnionType):
                    field_types = [arg for arg in typing.get_args(field_types) if arg is not types.NoneType]

                # validate that create_if_not_exists is not set for lists
                if extra_args.get("create_if_not_exists", False):
                    msg = "create_if_not_exists is not allowed for list fields"
                    raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)

            field_types = field_types if isinstance(field_types, list) else [field_types]

            for field_type in field_types:
                if not issubclass(field_type, HABApp.openhab.items.OpenhabItem | HABApp.openhab.items.Thing):
                    msg = f"Field {field_type} is not an OpenhabItem"
                    raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)

            # validate that only one type is given if create_if_not_exists is set
            if extra_args.get("create_if_not_exists", False) and len(field_types) > 1:
                msg = "If create_if_not_exists is set, only one type is allowed"
                raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)

        return data

    @pydantic.field_validator("*", mode="before")
    @classmethod
    def convert_to_oh_item(cls, var: str | HABApp.openhab.items.OpenhabItem, validation_info: pydantic.ValidationInfo) -> HABApp.openhab.items.OpenhabItem | None:
        """Convert to OpenHAB item.

        Args:
            var: variable given by the user
            validation_info: validation info given by pydantic

        Returns:
            variable converted to OpenHAB item

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationError: if type is not supported
        """
        extra_args = extra if (extra := cls.model_fields[validation_info.field_name].json_schema_extra) else {}
        create_if_not_exists = extra_args.get("create_if_not_exists", False)

        if create_if_not_exists:
            item_type = cls._get_type_of_field(validation_info.field_name).__qualname__.removesuffix("Item")
            return habapp_rules.core.helper.create_additional_item(var, item_type)

        if isinstance(var, list):
            return [cls._get_oh_item(itm) for itm in var]

        if issubclass(type(var), HABApp.openhab.items.OpenhabItem) or isinstance(var, str):
            return cls._get_oh_item(var)

        if var is None:
            return None

        msg = f"The following var is not supported: {var}"
        raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)

    @staticmethod
    def _get_oh_item(item: str | HABApp.openhab.items.OpenhabItem) -> HABApp.openhab.items.OpenhabItem:
        """Get OpenHAB item from string or OpenHAB item.

        Args:
            item: name of OpenHAB item or OpenHAB item

        Returns:
            OpenHAB item

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationError: if type is not supported
        """
        if isinstance(item, str):
            if ":" in item:
                return HABApp.openhab.items.Thing.get_item(item)
            return HABApp.openhab.items.OpenhabItem.get_item(item)

        return item

    @classmethod
    def _get_type_of_field(cls, field_name: str) -> type | list[type]:
        """Get type of field.

        Args:
            field_name: name of field

        Returns:
            type of field, NoneType will be ignored
        """
        field_type = cls.model_fields[field_name].annotation
        if isinstance(field_type, types.UnionType):
            field_type = [arg for arg in typing.get_args(field_type) if arg is not types.NoneType]
        return field_type


class ParameterBase(pydantic.BaseModel):
    """Base class for parameter config."""

    model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)


class ConfigBase(pydantic.BaseModel):
    """Base class for config objects."""

    items: ItemBase | None
    parameter: ParameterBase | None

    def __init__(self, **data: typing.Any) -> None:  # noqa: ANN401
        """Initialize the model.

        Args:
            data: data object given by pydantic

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationError: if validation fails
        """
        try:
            super().__init__(**data)
        except pydantic.ValidationError as exc:
            msg = f"Failed to validate model: {exc.errors()}"
            raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg) from exc
