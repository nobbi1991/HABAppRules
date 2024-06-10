"""Config models for light rules."""
import collections.abc
import logging
import typing

import HABApp.openhab.items
import pydantic

import habapp_rules.core.exceptions
import habapp_rules.core.pydantic_base

LOGGER = logging.getLogger(__name__)


class LightItems(habapp_rules.core.pydantic_base.ItemBase):
	"""Items for all light rules."""
	light: HABApp.openhab.items.DimmerItem | HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which controls the light")
	light_control: list[HABApp.openhab.items.DimmerItem] = pydantic.Field([], description="control items to improve manual detection")
	manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item to switch to manual mode and disable the automatic functions")
	presence_state: HABApp.openhab.items.StringItem = pydantic.Field(None, description="presence state set via habapp_rules.presence.Presence")
	day: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which is ON at day and OFF at night")
	sleeping_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="sleeping state set via habapp_rules.system.sleep.Sleep")
	doors: list[HABApp.openhab.items.ContactItem] = pydantic.Field([], description="door items for switching on the light if the door is opening")
	motion: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="motion sensor to enable light if motion is detected")
	state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item to store the current state of the state machine", json_schema_extra={"create_if_not_exists": True})


class BrightnessTimeout(pydantic.BaseModel):
	"""Define brightness and timeout for light states."""
	brightness: int | bool = pydantic.Field(..., description="brightness which should be set. If bool ON will be sent for True and OFF for False")
	timeout: float = pydantic.Field(..., description="Timeout / max time in seconds until switch off")

	def __init__(self, brightness: int | bool, timeout: float):
		"""Initialize BrightnessTimeout without kwargs

		:param brightness: brightness value
		:param timeout: timeout value
		"""
		super().__init__(brightness=brightness, timeout=timeout)

	@pydantic.model_validator(mode="after")
	def validata_model(self) -> typing.Self:
		"""Validate brightness and timeout

		:raises AssertionError: if brightness and timeout are not valid
		:return: self
		"""
		if self.brightness is False or self.brightness == 0:
			# Default if the light should be switched off e.g. for leaving / sleeping
			if not self.timeout:
				self.timeout = 0.5

		if not self.timeout:
			raise AssertionError(f"Brightness and timeout are not valid: brightness = {self.brightness} | timeout = {self.timeout}")
		return self


class FunctionConfig(pydantic.BaseModel):
	"""Define brightness and timeout values for one function."""
	day: BrightnessTimeout | None = pydantic.Field(..., description="config for day. If None the light will not be switched on during the day")
	night: BrightnessTimeout | None = pydantic.Field(..., description="config for night. If None the light will not be switched on during the night")
	sleeping: BrightnessTimeout | None = pydantic.Field(..., description="config for sleeping. If None the light will not be switched on during sleeping")


class LightParameter(habapp_rules.core.pydantic_base.ParameterBase):
	"""Parameter for all light rules.

	For all parameter which have the following type: FunctionConfig | None -> If None this state will be disabled for the rule
	"""
	on: FunctionConfig = pydantic.Field(FunctionConfig(day=BrightnessTimeout(True, 14 * 3600), night=BrightnessTimeout(80, 10 * 3600), sleeping=BrightnessTimeout(20, 3 * 3600)),
	                                    description="values which are used if the light is switched on manually")
	pre_off: FunctionConfig | None = pydantic.Field(FunctionConfig(day=BrightnessTimeout(50, 10), night=BrightnessTimeout(40, 7), sleeping=BrightnessTimeout(10, 7)), description="values which are used if the light changes pre_off state")
	leaving: FunctionConfig | None = pydantic.Field(FunctionConfig(day=BrightnessTimeout(False, 0), night=BrightnessTimeout(False, 0), sleeping=BrightnessTimeout(False, 0)), description="values which are used if the light changes to leaving state")
	pre_sleep: FunctionConfig | None = pydantic.Field(FunctionConfig(day=BrightnessTimeout(False, 10), night=BrightnessTimeout(False, 10), sleeping=None), description="values which are used if the light changes to pre_sleep state")
	pre_sleep_prevent: collections.abc.Callable[[], bool] | HABApp.openhab.items.OpenhabItem | None = pydantic.Field(None, description="Enable pre sleep prevent -> disable pre sleep if True")
	motion: FunctionConfig | None = pydantic.Field(None, description="values which are used if the light changes to motion state")
	door: FunctionConfig | None = pydantic.Field(None, description="values which are used if the light is enabled via a door opening")
	off_at_door_closed_during_leaving: bool = pydantic.Field(False, description="this can be used to switch lights off, when door is closed in leaving state")
	hand_off_lock_time: int = pydantic.Field(20, description="time in seconds where door / motion switch on is disabled after a manual OFF")

	@pydantic.field_validator("on", mode="after")
	@classmethod
	def validate_on(cls, value: FunctionConfig) -> FunctionConfig:
		"""Validate config for on-state

		:param value: given value
		:return: validated value
		:raises AssertionError: if on is not valid
		"""
		if any(conf is None for conf in [value.day, value.night, value.sleeping]):
			raise AssertionError("For function 'on' all brightness / timeout values must be set.")
		return value

	@pydantic.field_validator("pre_sleep", mode="after")
	@classmethod
	def validate_pre_sleep(cls, value: FunctionConfig | None) -> FunctionConfig | None:
		"""Validate pre_sleep config

		:param value: value of pre sleep
		:raises AssertionError: if pre_sleep is not valid
		:return: validated value
		"""
		if value is None:
			return value

		if value.sleeping is not None:
			LOGGER.warning("It's not allowed to set brightness / timeout for pre_sleep.sleeping. Set it to None")
			value.sleeping = None

		return value


class LightConfig(habapp_rules.core.pydantic_base.ConfigBase):
	"""Config for all light rules."""
	items: LightItems = pydantic.Field(..., description="items for all light rules")
	parameter: LightParameter = pydantic.Field(LightParameter(), description="parameter for all light rules")

	@pydantic.model_validator(mode="after")
	def validate_config(self) -> typing.Self:
		"""Validate config

		:raises AssertionError: if config is not valid
		:return: config if valid
		"""
		if self.items.motion is not None and self.parameter.motion is None:
			raise AssertionError("item motion is given, but not configured via parameter")

		if len(self.items.doors) and self.parameter.door is None:
			raise AssertionError("item door is given, but not configured via parameter")

		if self.items.sleeping_state is not None and self.parameter.pre_sleep is None:
			raise AssertionError("item sleeping_state is given, but not configured via parameter")

		if self.items.presence_state is not None and self.parameter.leaving is None:
			raise AssertionError("item presence_state is given, but not configured via parameter")

		return self
