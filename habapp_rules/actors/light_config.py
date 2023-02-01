import collections.abc
import dataclasses
import logging
import typing

import HABApp.util

import habapp_rules.actors.state_observer
import habapp_rules.common.exceptions
import habapp_rules.common.helper
import habapp_rules.common.state_machine_rule
import habapp_rules.system

LOGGER = logging.getLogger("HABApp.actors.light")
LOGGER.setLevel("DEBUG")

BrightnessTypes = typing.Union[list[typing.Union[float, bool]], float, bool]


@dataclasses.dataclass
class BrightnessTimeout:
	brightness: int | bool
	timeout: float

	def __post_init__(self):
		"""Check if all values where set correct."""
		if not self.brightness or not self.timeout:
			raise habapp_rules.common.exceptions.HabAppRulesConfigurationException


@dataclasses.dataclass
class FunctionConfig:
	day: BrightnessTimeout | None
	night: BrightnessTimeout | None
	sleeping: BrightnessTimeout | None


@dataclasses.dataclass
class LightConfig:
	on: FunctionConfig  # pylint: disable=invalid-name
	pre_off: FunctionConfig | None
	leaving: FunctionConfig | None
	pre_sleep: FunctionConfig | None
	pre_sleep_prevent: collections.abc.Callable[[], bool] | HABApp.openhab.items.OpenhabItem | None = None

	def __post_init__(self):
		if not all(dataclasses.asdict(self.on).values()):
			raise habapp_rules.common.exceptions.HabAppRulesConfigurationException("For function 'on' all brightness / timeout values must be set.")

		if self.pre_sleep.sleeping:
			LOGGER.warning("It's not allowed to set brightness / timeout for pre_sleep.sleeping. Set it to None")
			self.pre_sleep.sleeping = None


CONFIG_DEFAULT = LightConfig(
	on=FunctionConfig(day=BrightnessTimeout(True, 600), night=BrightnessTimeout(80, 180), sleeping=BrightnessTimeout(20, 60)),
	pre_off=FunctionConfig(day=BrightnessTimeout(50, 10), night=BrightnessTimeout(40, 7), sleeping=BrightnessTimeout(10, 7)),
	leaving=FunctionConfig(day=None, night=None, sleeping=None),
	pre_sleep=FunctionConfig(day=None, night=None, sleeping=None),
)

CONFIG_TEST = LightConfig(
	on=FunctionConfig(day=BrightnessTimeout(True, 10), night=BrightnessTimeout(80, 8), sleeping=BrightnessTimeout(20, 6)),
	pre_off=FunctionConfig(day=BrightnessTimeout(50, 7), night=BrightnessTimeout(40, 6), sleeping=BrightnessTimeout(10, 5)),
	leaving=FunctionConfig(day=BrightnessTimeout(90, 10), night=BrightnessTimeout(50, 10), sleeping=None),
	pre_sleep=FunctionConfig(day=BrightnessTimeout(40, 10), night=BrightnessTimeout(30, 7), sleeping=None)
)
