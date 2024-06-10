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
	def check_all_fields_oh_items(cls, data: typing.Any) -> typing.Any:
		"""Validate that all fields are OpenHAB items.

		All items must be subclasses of `HABApp.openhab.items.OpenhabItem`.
		If create_if_not_exists is set, only one type is allowed.
		For lists, only one type is allowed.

		:param data: data object given by pydantic
		:return: data object
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if validation fails
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
					raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("create_if_not_exists is not allowed for list fields")

			field_types = field_types if isinstance(field_types, list) else [field_types]

			for field_type in field_types:
				if not issubclass(field_type, HABApp.openhab.items.OpenhabItem):
					raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"Field {field_type} is not an OpenhabItem")

			# validate that only one type is given if create_if_not_exists is set
			if extra_args.get("create_if_not_exists", False) and len(field_types) > 1:
				raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("If create_if_not_exists is set, only one type is allowed")

		return data

	@pydantic.field_validator("*", mode="before")
	@classmethod
	def convert_to_oh_item(cls, var: str | HABApp.openhab.items.OpenhabItem, validation_info: pydantic.ValidationInfo) -> HABApp.openhab.items.OpenhabItem | None:
		"""Convert to OpenHAB item.

		:param var: variable given by the user
		:param validation_info: validation info given by pydantic
		:return: variable converted to OpenHAB item
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if type is not supported
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

		raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"The following var is not supported: {var}")

	@staticmethod
	def _get_oh_item(item: str | HABApp.openhab.items.OpenhabItem) -> HABApp.openhab.items.OpenhabItem:
		"""get OpenHAB item from string or OpenHAB item

		:param item: name of OpenHAB item or OpenHAB item
		:return: OpenHAB item
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if type is not supported
		"""
		return item if isinstance(item, HABApp.openhab.items.OpenhabItem) else HABApp.openhab.items.OpenhabItem.get_item(item)

	@classmethod
	def _get_type_of_field(cls, field_name: str) -> type | list[type]:
		"""Get type of field

		:param field_name: name of field
		:return: type of field, NoneType will be ignored
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

# todo raise habapp_rules.core.exceptions.HabAppRulesConfigurationException instead ValidationError
