"""Configuration of shading objects."""
import copy
import typing

import HABApp.openhab.items
import pydantic

import habapp_rules.core.pydantic_base


class ShadingPosition(pydantic.BaseModel):
	"""Position of shading object"""
	position: float | bool | None = pydantic.Field(..., description="target position")  # todo maybe remove bool?! and why None?!
	slat: float | None = pydantic.Field(None, description="target slat position")

	def __init__(self, position=float | bool | None, slat: float | None = None) -> None:
		super().__init__(position=position, slat=slat)


class ShadingItems(habapp_rules.core.pydantic_base.ItemBase):
	shading_position: HABApp.openhab.items.RollershutterItem | HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="")
	slat: HABApp.openhab.items.DimmerItem | None = pydantic.Field(None, description="")
	manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="")
	shading_position_control: list[HABApp.openhab.items.RollershutterItem | HABApp.openhab.items.DimmerItem] = pydantic.Field([], description="")
	shading_position_group: list[HABApp.openhab.items.RollershutterItem | HABApp.openhab.items.DimmerItem] = pydantic.Field([], description="")
	wind_alarm: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="")
	sun_protection: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="")
	sun_protection_slat: HABApp.openhab.items.DimmerItem | None = pydantic.Field(None, description="")
	sleeping_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="")
	night: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="")
	door: HABApp.openhab.items.ContactItem | None = pydantic.Field(None, description="")
	summer: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="")
	hand_manual_is_active_feedback: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="")
	state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item to store the current state of the state machine", json_schema_extra={"create_if_not_exists": True})


class ShadingParameter(habapp_rules.core.pydantic_base.ParameterBase):
	pos_auto_open: ShadingPosition = pydantic.Field(ShadingPosition(0, 0), description="")
	pos_wind_alarm: ShadingPosition | None = pydantic.Field(ShadingPosition(0, 0), description="")
	pos_sleeping_night: ShadingPosition | None = pydantic.Field(ShadingPosition(100, 100), description="")
	pos_sleeping_day: ShadingPosition | None = pydantic.Field(None, description="")
	pos_sun_protection: ShadingPosition | None = pydantic.Field(ShadingPosition(100, None), description="")
	pos_night_close_summer: ShadingPosition | None = pydantic.Field(None, description="")
	pos_night_close_winter: ShadingPosition | None = pydantic.Field(ShadingPosition(100, 100), description="")
	pos_door_open: ShadingPosition | None = pydantic.Field(ShadingPosition(0, 0), description="")
	manual_timeout: int = pydantic.Field(24 * 3600, description="")
	door_post_time: int = pydantic.Field(5 * 60, description="")
	value_tolerance: int = pydantic.Field(0, description="")

	@pydantic.field_validator("door_post_time")
	@classmethod
	def check_post_time(cls, v: int) -> int:
		if v in {0, None}:
			return 1
		return v

	@pydantic.model_validator(mode="after")
	def validate_model(self) -> typing.Self:
		if self.pos_sleeping_night and not self.pos_sleeping_day:
			self.pos_sleeping_day = copy.deepcopy(self.pos_sleeping_night)
		return self


class ShadingConfig(habapp_rules.core.pydantic_base.ConfigBase):
	"""Config for shading objects."""
	items: ShadingItems
	parameter: ShadingParameter

	@pydantic.model_validator(mode="after")
	def validate_model(self) -> typing.Self:
		if self.parameter.pos_night_close_summer is not None and self.items.summer is None:
			raise AssertionError("Night close position is set for summer, but item for summer / winter is missing!")

		# check if the correct items are given for sun protection mode # todo move this check to raffstore
		# if (self.items.sun_protection is None) != (self.items.sun_protection_slat is None):
		# 	raise AssertionError("Ether items.sun_protection AND items.sun_protection_slat item must be given or None of them.") # todo really?

		return self


CONFIG_DEFAULT_ELEVATION_SLAT_WINTER = [(0, 100), (4, 100), (8, 90), (18, 80), (26, 70), (34, 60), (41, 50), (42, 50), (90, 50), ]  # todo pydantic?!
CONFIG_DEFAULT_ELEVATION_SLAT_SUMMER = [(0, 100), (4, 100), (8, 100), (18, 100), (26, 100), (34, 90), (41, 80), (42, 80), (90, 80), ]
