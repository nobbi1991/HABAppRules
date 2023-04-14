"""Configuration of lights."""

import collections.abc
import dataclasses
import logging
import typing

import HABApp.util

import habapp_rules.actors.state_observer
import habapp_rules.core.exceptions
import habapp_rules.core.helper
import habapp_rules.core.state_machine_rule
import habapp_rules.system

LOGGER = logging.getLogger(__name__)

BrightnessTypes = typing.Union[list[typing.Union[float, bool]], float, bool]


@dataclasses.dataclass
class BrightnessTimeout:
	"""Define brightness and timeout for light states."""
	brightness: int | bool
	timeout: float

	def __post_init__(self):
		"""Check if all values where set correct.

		:raises habapp_rules.common.exceptions.HabAppRulesConfigurationException: if config is not valid."""
		if self.brightness is False:
			# Default if the light should be switched off e.g. for leaving / sleeping
			if not self.timeout:
				self.timeout = 0.5
			return

		if not self.brightness or not self.timeout:
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"Brightness and timeout are not valid: brightness = {self.brightness} | timeout = {self.timeout}")


@dataclasses.dataclass
class FunctionConfig:
	"""Define brightness and timeout values for one function."""
	day: BrightnessTimeout | None
	night: BrightnessTimeout | None
	sleeping: BrightnessTimeout | None


@dataclasses.dataclass
class LightConfig:
	"""Configuration for basic lights"""
	on: FunctionConfig  # pylint: disable=invalid-name
	pre_off: FunctionConfig | None
	leaving: FunctionConfig | None
	pre_sleep: FunctionConfig | None
	pre_sleep_prevent: collections.abc.Callable[[], bool] | HABApp.openhab.items.OpenhabItem | None = None

	def __post_init__(self):
		"""Check if light config is correct.

		:raises habapp_rules.common.exceptions.HabAppRulesConfigurationException: if config is not correct."""
		if not self.on or not all(dataclasses.asdict(self.on).values()):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("For function 'on' all brightness / timeout values must be set.")

		if getattr(self.pre_sleep, "sleeping", None):
			LOGGER.warning("It's not allowed to set brightness / timeout for pre_sleep.sleeping. Set it to None")
			self.pre_sleep.sleeping = None


@dataclasses.dataclass
class LightConfigExtended(LightConfig):
	"""Configuration for extended lights."""
	motion: FunctionConfig | None = None
	door: FunctionConfig | None = None
	off_at_door_closed_during_leaving: bool = False  # this can be used to switch lights off, when door is closed in leaving state
	hand_off_lock_time: int = 20


CONFIG_DEFAULT = LightConfig(
	on=FunctionConfig(day=BrightnessTimeout(True, 600), night=BrightnessTimeout(80, 180), sleeping=BrightnessTimeout(20, 60)),
	pre_off=FunctionConfig(day=BrightnessTimeout(50, 10), night=BrightnessTimeout(40, 7), sleeping=BrightnessTimeout(10, 7)),
	leaving=FunctionConfig(day=BrightnessTimeout(False, 0), night=BrightnessTimeout(False, 0), sleeping=BrightnessTimeout(False, 0)),
	pre_sleep=FunctionConfig(day=BrightnessTimeout(False, 10), night=BrightnessTimeout(False, 10), sleeping=None),
)

CONFIG_DEFAULT_EXTENDED = LightConfigExtended(
	on=FunctionConfig(day=BrightnessTimeout(True, 600), night=BrightnessTimeout(80, 180), sleeping=BrightnessTimeout(20, 60)),
	pre_off=FunctionConfig(day=BrightnessTimeout(50, 10), night=BrightnessTimeout(40, 7), sleeping=BrightnessTimeout(10, 7)),
	leaving=FunctionConfig(day=BrightnessTimeout(False, 0), night=BrightnessTimeout(False, 0), sleeping=BrightnessTimeout(False, 0)),
	pre_sleep=FunctionConfig(day=BrightnessTimeout(False, 10), night=BrightnessTimeout(False, 10), sleeping=None),
	motion=FunctionConfig(day=BrightnessTimeout(True, 600), night=BrightnessTimeout(80, 180), sleeping=BrightnessTimeout(20, 60)),
	door=FunctionConfig(day=BrightnessTimeout(True, 60), night=BrightnessTimeout(80, 30), sleeping=None),
	off_at_door_closed_during_leaving=False
)
