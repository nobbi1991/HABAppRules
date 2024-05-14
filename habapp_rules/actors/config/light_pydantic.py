import collections.abc
import typing

import HABApp.openhab.items
import pydantic

import habapp_rules.core.exceptions
import habapp_rules.core.pydantic_base


class LightItems(habapp_rules.core.pydantic_base.ItemBase):
	"""Items for all light rules."""
	light: HABApp.openhab.items.DimmerItem | HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="OpenHAB item which controls the light")  # todo how to handle multiple item types. e.g. Switch / Dimmer
	light_control: list[HABApp.openhab.items.DimmerItem] = pydantic.Field([], description="")  # todo add description
	manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="")  # todo add description
	presence_state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="")  # todo add description
	day: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="")  # todo add description
	sleeping_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="")  # todo add description
	doors: list[HABApp.openhab.items.ContactItem] = pydantic.Field([], description="")  # todo add description
	motion: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="")  # todo add description
	state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="OpenHAB item to store the current state of the state machine", json_schema_extra={"create_if_not_exists": True})


class BrightnessTimeout(pydantic.BaseModel):
	"""Define brightness and timeout for light states."""
	brightness: int | bool = pydantic.Field(..., description="")  # todo add description
	timeout: float = pydantic.Field(..., description="")  # todo add description

	def __init__(self, brightness: int | bool, timeout: float):
		super().__init__(brightness=brightness, timeout=timeout)

	@pydantic.model_validator(mode='after')
	def validata_model(self) -> typing.Self:
		"""Validate brightness and timeout

		:return: self
		"""
		if self.brightness is False:
			# Default if the light should be switched off e.g. for leaving / sleeping
			if not self.timeout:
				self.timeout = 0.5

		if not self.timeout:
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"Brightness and timeout are not valid: brightness = {self.brightness} | timeout = {self.timeout}")
		return self


class FunctionConfig(pydantic.BaseModel):
	"""Define brightness and timeout values for one function."""
	day: BrightnessTimeout | None = pydantic.Field(..., description="")  # todo add description
	night: BrightnessTimeout | None = pydantic.Field(..., description="")  # todo add description
	sleeping: BrightnessTimeout | None = pydantic.Field(..., description="")  # todo add description


class LightParameter(habapp_rules.core.pydantic_base.ParameterBase):
	"""Parameter for all light rules."""
	on: FunctionConfig = pydantic.Field(FunctionConfig(day=BrightnessTimeout(True, 14 * 3600), night=BrightnessTimeout(80, 10 * 3600), sleeping=BrightnessTimeout(20, 3 * 3600)), description="")  # todo add description
	pre_off: FunctionConfig | None = pydantic.Field(FunctionConfig(day=BrightnessTimeout(50, 10), night=BrightnessTimeout(40, 7), sleeping=BrightnessTimeout(10, 7)), description="")  # todo add description
	leaving: FunctionConfig | None = pydantic.Field(FunctionConfig(day=BrightnessTimeout(False, 0), night=BrightnessTimeout(False, 0), sleeping=BrightnessTimeout(False, 0)), description="")  # todo add description
	pre_sleep: FunctionConfig | None = pydantic.Field(FunctionConfig(day=BrightnessTimeout(False, 10), night=BrightnessTimeout(False, 10), sleeping=None), description="")  # todo add description
	pre_sleep_prevent: collections.abc.Callable[[], bool] | HABApp.openhab.items.OpenhabItem | None = pydantic.Field(None, description="")  # todo add description
	motion: FunctionConfig | None = pydantic.Field(None, description="")  # todo add description
	door: FunctionConfig | None = pydantic.Field(None, description="")  # todo add description
	off_at_door_closed_during_leaving: bool = pydantic.Field(False, description="this can be used to switch lights off, when door is closed in leaving state")
	hand_off_lock_time: int = pydantic.Field(20, description="")  # todo add description


class LightConfig(habapp_rules.core.pydantic_base.ConfigBase):
	"""Config for all light rules."""
	items: LightItems = pydantic.Field(..., description="")  # todo add description
	parameter: LightParameter = pydantic.Field(LightParameter(), description="")  # todo add description
	# todo add validation
