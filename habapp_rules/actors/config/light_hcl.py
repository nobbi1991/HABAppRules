"""Config for HCL color"""
import typing

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class HclItemsTime(habapp_rules.core.pydantic_base.ItemBase):
	"""Items for HCL color which depends on time"""
	color: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="HCL color which will be set by the HCL rule")
	manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="switch item to disable all automatic functions")
	sleep_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sleep state item")
	focus: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="focus state item")
	switch_on: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="switch item which triggers a color update if switched on")
	state: HABApp.openhab.items.StringItem | None = pydantic.Field(..., description="state item for storing the current state")


class HclItemsElevation(HclItemsTime):
	"""Items for HCL color which depends on sun elevation"""
	elevation: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="sun elevation")


class HclParameterElevation(habapp_rules.core.pydantic_base.ParameterBase):
	"""Parameter for HCL color"""
	color_map: list[tuple[float, float]] = pydantic.Field(..., description="")  # todo add description
	hand_timeout: int = pydantic.Field(18_000, description="", gt=0)  # 5 hours # todo add description
	sleep_color: float = pydantic.Field(2500, description="", gt=0)  # todo add description
	post_sleep_timeout: int = pydantic.Field(1, description="", gt=0)  # todo add description
	focus_color: float = pydantic.Field(6000, description="", gt=0)  # todo add description, # todo set to 0 if None

	@pydantic.model_validator(mode="after")
	def validate_model(self) -> typing.Self:
		self.color_map = sorted(self.color_map, key=lambda x: x[0])
		return self


class HclParameterTime(HclParameterElevation):
	"""Parameter for HCL color which depends on time"""
	shift_weekend_holiday: bool = pydantic.Field(False, description="")  # todo add description


class HclConfigElevation(habapp_rules.core.pydantic_base.ConfigBase):
	"""Config for HCL color which depends on sun elevation"""
	items: HclItemsElevation
	parameter: HclParameterElevation


class HclConfigTime(HclConfigElevation):
	"""Config for HCL color which depends on time"""
	items: HclItemsTime
	parameter: HclParameterTime
