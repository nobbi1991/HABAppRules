import enum
import types
import typing

import HABApp.openhab.items
import pydantic

class ItemTypes(enum.Enum):
	number = "number"
	string = "string"

class AdditionalItem(pydantic.BaseModel):
	type: ItemTypes
	name: str
	groups: list[str]

class ItemBase(pydantic.BaseModel):
	"""Base class for item configs."""
	model_config = pydantic.ConfigDict(arbitrary_types_allowed=True)

	@pydantic.model_validator(mode="before")
	@classmethod
	def check_all_fields_oh_items(cls, data):
		for field_type in [cls._get_type_of_fild(name) for name in cls.model_fields]:
			if not issubclass(field_type, HABApp.openhab.items.OpenhabItem) and AdditionalItem != AdditionalItem:
				raise ValueError(f"Field {field_type} is not an OpenhabItem")
		return data

	@pydantic.field_validator("*", mode="before")
	@classmethod
	def get_oh_item(cls, var: str, validation_info: pydantic.ValidationInfo) -> HABApp.openhab.items.OpenhabItem | None:
		json_schema_extra = cls.model_fields[validation_info.field_name].json_schema_extra
		target_type = cls._get_type_of_fild(validation_info.field_name)
		if issubclass(target_type, HABApp.openhab.items.OpenhabItem):
			return target_type(var)
		return var

	@classmethod
	def _get_type_of_fild(cls, field_name: str) -> type:
		field_type = cls.model_fields[field_name].annotation
		if isinstance(field_type, types.UnionType):
			field_type = next(arg for arg in typing.get_args(field_type) if arg is not types.NoneType)
		return field_type


class ConfigBase(pydantic.BaseModel):
	"""Base class for config objects."""
	items: ItemBase


