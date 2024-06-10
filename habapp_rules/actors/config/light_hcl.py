"""Config models for HCL color rules."""
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
	color_map: list[tuple[float, float]] = pydantic.Field(..., description="Color mapping. The first value is the sun elevation, the second is the HCL color")
	hand_timeout: int = pydantic.Field(18_000, description="hand timeout. After this time the HCL light rule will fall back to auto mode", gt=0)  # 5 hours
	sleep_color: float = pydantic.Field(2500, description="color if sleeping is active", gt=0)
	post_sleep_timeout: int = pydantic.Field(1, description="time after sleeping was active where the sleeping color will be set", gt=0)
	focus_color: float = pydantic.Field(6000, description="color if focus is active", gt=0)

	@pydantic.model_validator(mode="after")
	def validate_model(self) -> typing.Self:
		"""Sort color map

		:return: model with sorted color map
		"""
		self.color_map = sorted(self.color_map, key=lambda x: x[0])
		return self


class HclParameterTime(HclParameterElevation):
	"""Parameter for HCL color which depends on time"""
	shift_weekend_holiday: bool = pydantic.Field(False, description="If this is active the color will shift on weekends and holidays for one hour")


class HclConfigElevation(habapp_rules.core.pydantic_base.ConfigBase):
	"""Config for HCL color which depends on sun elevation"""
	items: HclItemsElevation
	parameter: HclParameterElevation


class HclConfigTime(HclConfigElevation):
	"""Config for HCL color which depends on time"""
	items: HclItemsTime
	parameter: HclParameterTime
