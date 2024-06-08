import logging
import typing

import HABApp
import pydantic

import habapp_rules.core.pydantic_base

LOGGER = logging.getLogger(__name__)


class _ItemsBase(habapp_rules.core.pydantic_base.ItemBase):
	output: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="output item")
	threshold: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="threshold item")


class BrightnessItems(_ItemsBase):
	brightness: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="brightness item")


class TemperatureDifferenceItems(_ItemsBase):
	temperatures: list[HABApp.openhab.items.NumberItem] = pydantic.Field(..., description="temperature items")

	@pydantic.model_validator(mode="after")
	def validate_temperature_items(self) -> typing.Self:
		"""Validate that at least two temperature items are given."""
		if len(self.temperatures) < 2:
			raise ValueError("At least two temperature items are required!")
		return self


class BrightnessParameter(habapp_rules.core.pydantic_base.ParameterBase):
	threshold: float | None = pydantic.Field(None, description="threshold value")
	hysteresis: float = pydantic.Field(0.0, description="hysteresis value")
	filter_tau: int = pydantic.Field(30 * 60, description="filter constant for the exponential filter. Default is set to 30 minutes")
	filter_instant_increase: bool = pydantic.Field(True, description="if set to True, increase of input values will not be filtered")
	filter_instant_decrease: bool = pydantic.Field(False, description="if set to True, decrease of input values will not be filtered")
	filtered_signal_groups: list[str] = pydantic.Field([], description="group names where the filtered signal will be added")


class TemperatureDifferenceParameter(BrightnessParameter):
	ignore_old_values_time: int | None = pydantic.Field(None, description="ignores values which are older than the given time in seconds. If None, all values will be taken")


class _ConfigBase(habapp_rules.core.pydantic_base.ConfigBase):
	items: BrightnessItems | TemperatureDifferenceItems = pydantic.Field(..., description="items for sun sensor")
	parameter: BrightnessParameter | TemperatureDifferenceParameter = pydantic.Field(..., description="parameter for sun sensor")

	@pydantic.model_validator(mode="after")
	def validate_threshold(self) -> typing.Self:
		"""Validate threshold."""
		if (self.items.threshold is None) == (self.parameter.threshold is None):
			raise ValueError("The threshold must be set ether with the parameter or with the item, both are not allowed")
		return self

	@property
	def threshold(self) -> float:
		"""Get threshold."""
		if self.parameter.threshold:
			return self.parameter.threshold

		if self.items.threshold.value is None:
			LOGGER.warning("Threshold item has no value set. Setting threshold to infinity")
			return float("inf")

		return self.items.threshold.value


class BrightnessConfig(_ConfigBase):
	items: BrightnessItems = pydantic.Field(..., description="items for sun sensor which uses brightness as input")
	parameter: BrightnessParameter = pydantic.Field(BrightnessParameter(), description="parameter for sun sensor which uses brightness as input")


class TemperatureDifferenceConfig(_ConfigBase):
	items: TemperatureDifferenceItems = pydantic.Field(..., description="items for sun sensor which uses temperature items as input")
	parameter: TemperatureDifferenceParameter = pydantic.Field(TemperatureDifferenceParameter(), description="parameter for sun sensor which uses temperature items as input")

############################ SunPositionFilter ###############################


class SunPositionWindow(pydantic.BaseModel):
	"""Class for defining min / max values for azimuth and elevation."""
	azimuth_min: float = pydantic.Field(..., description="Starting value for azimuth", ge=0.0, le=360.0)
	azimuth_max: float = pydantic.Field(..., description="End value for azimuth", ge=0.0, le=360.0)
	elevation_min: float = pydantic.Field(0.0, description="Starting value for elevation", ge=-90.0, le=90.0)
	elevation_max: float = pydantic.Field(90.0, description="End value for elevation", ge=-90.0, le=90.0)

	def __init__(self, azimuth_min: float, azimuth_max: float, elevation_min: float = 0.0, elevation_max: float = 90.0) -> None:
		"""Init of class for defining min / max values for azimuth and elevation."""
		super().__init__(azimuth_min=azimuth_min, azimuth_max=azimuth_max, elevation_min=elevation_min, elevation_max=elevation_max)

	@pydantic.model_validator(mode="after")
	def validate(self) -> typing.Self:
		"""Validate values."""
		if self.azimuth_min > self.azimuth_max:
			LOGGER.warning(f"azimuth_min should be smaller than azimuth_max -> min / max will be swapped. Given values: azimuth_min = {self.azimuth_min} | azimuth_max = {self.azimuth_max}")
			min_orig = self.azimuth_min
			max_orig = self.azimuth_max
			self.azimuth_min = max_orig
			self.azimuth_max = min_orig

		if self.elevation_min > self.elevation_max:
			LOGGER.warning(f"elevation_min should be smaller than elevation_max -> min / max will be swapped. Given values: elevation_min = {self.elevation_min} | elevation_max = {self.elevation_max}")
			min_orig = self.elevation_min
			max_orig = self.elevation_max
			self.elevation_min = max_orig
			self.elevation_max = min_orig
		return self


class SunPositionItems(habapp_rules.core.pydantic_base.ItemBase):
	azimuth: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="sun azimuth item")
	elevation: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="sun elevation item")
	input: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="input item (sun protection required)")
	output: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="output item (sun protection required and sun in the configured azimuth / elevation window)")


class SunPositionParameter(habapp_rules.core.pydantic_base.ParameterBase):
	sun_position_window: SunPositionWindow | list[SunPositionWindow] = pydantic.Field(..., description="sun position window, where the sun hits the target")

	@property
	def sun_position_windows(self) -> list[SunPositionWindow]:
		"""Get sun position windows."""
		return self.sun_position_window if isinstance(self.sun_position_window, list) else [self.sun_position_window]


class SunPositionConfig(habapp_rules.core.pydantic_base.ConfigBase):
	items: SunPositionItems = pydantic.Field(..., description="items for sun position filter")
	parameter: SunPositionParameter = pydantic.Field(..., description="parameter for sun position filter")
