"""Rules to handle sun sensors."""
import dataclasses
import logging

import HABApp

import habapp_rules.common.filter
import habapp_rules.common.hysteresis
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule

LOGGER = logging.getLogger(__name__)


@dataclasses.dataclass
class SunPositionWindow:
	"""Class for defining min / max values for azimuth and elevation."""
	azimuth_min: float
	azimuth_max: float
	elevation_min: float = 0.0
	elevation_max: float = 90.0

	def __post_init__(self) -> None:
		"""Check if the dataclass was initialized correctly."""
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


class _SensorBase(HABApp.Rule):
	"""Base class for sun sensors."""

	def __init__(self, name_input: str, name_output: str, threshold: str | float, filter_tau: int, filter_instant_increase: bool = True, filter_instant_decrease: bool = False) -> None:
		"""Init of base class for sun sensors.

		:param name_input: name of OpenHAB input item (NumberItem)
		:param name_output: name of OpenHAB output item (SwitchItem)
		:param threshold: threshold for the temperature difference which is supposed that sun is shining. Can be given as float value or name of OpenHAB NumberItem
		:param filter_tau: filter constant for the exponential filter. Default is set to 20 minutes
		:param filter_instant_increase: if set to True, increase of input values will not be filtered
		:param filter_instant_decrease: if set to True, decrease of input values will not be filtered
		"""
		# init HABApp Rule
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_output)

		# init exponential filter
		name_input_exponential_filtered = f"H_{name_input.removeprefix('H_')}_filtered"
		HABApp.openhab.interface.create_item("Number", name_input_exponential_filtered, name_input_exponential_filtered.replace("_", " "))
		habapp_rules.common.filter.ExponentialFilter(name_input, name_input_exponential_filtered, filter_tau, filter_instant_increase, filter_instant_decrease)

		# init items
		self._item_input_filtered = HABApp.openhab.items.NumberItem.get_item(name_input_exponential_filtered)
		self._item_output = HABApp.openhab.items.SwitchItem.get_item(name_output)
		self._item_threshold = HABApp.openhab.items.NumberItem.get_item(threshold) if isinstance(threshold, str) else None

		# attributes
		self._threshold = self._item_threshold.value if self._item_threshold is not None else threshold

		# callbacks
		self._item_input_filtered.listen_event(self._cb_input_filtered, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_threshold is not None:
			self._item_threshold.listen_event(self._cb_threshold, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _send_output(self, new_value: str) -> None:
		"""Send output if different.

		:param new_value: new value which should be sent
		"""
		if new_value != self._item_output.value:
			self._item_output.oh_send_command(new_value)
			self._instance_logger.debug(f"Set output '{self._item_output.name}' to {new_value}")

	def _cb_input_filtered(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the filtered input value changed.

		:param event: trigger event
		"""
		if self._threshold is None:
			self._instance_logger.debug("The threshold value is None -> Can not check if new value is greater / smaller then the threshold")
			return

		value = "ON" if event.value >= self._threshold else "OFF"
		self._send_output(value)

	def _cb_threshold(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the threshold changed.

		:param event: trigger event
		"""
		self._threshold = event.value


class SensorBrightness(_SensorBase):
	"""Rules class to set sun protection depending on brightness level.

	# Items:
	Number    brightness                    "Current brightness [%d lux]"       {channel="..."}
	Number    brightness_threshold          "Brightness threshold [%d lux]"
	Switch    sun_protection_brightness     "Sun protection brightness [%s]     {channel="..."}

	# Rule init:
	habapp_rules.sensors.sun.SensorBrightness("brightness", "sun_protection_brightness", "brightness_threshold")
	"""

	def __init__(self, name_brightness: str, name_output: str, threshold: str | float, filter_tau: int = 20 * 60, filter_instant_increase: bool = True, filter_instant_decrease: bool = False) -> None:
		"""Init of sun sensor which takes a brightness value

		:param name_brightness: name of OpenHAB brightness item (NumberItem)
		:param name_output: name of OpenHAB output item (SwitchItem)
		:param threshold: threshold for the temperature difference which is supposed that sun is shining. Can be given as float value or name of OpenHAB NumberItem
		:param filter_tau: filter constant for the exponential filter. Default is set to 20 minutes
		:param filter_instant_increase: if set to True, increase of input values will not be filtered
		:param filter_instant_decrease: if set to True, decrease of input values will not be filtered
		"""
		_SensorBase.__init__(self, name_brightness, name_output, threshold, filter_tau, filter_instant_increase, filter_instant_decrease)


class SensorTemperatureDifference(_SensorBase):
	"""Rules class to set sun protection depending on temperature difference. E.g. temperature in the sun / temperature in the shadow.

	# Items:
	Number    temperature_sun               "Temperature sun [%.1f °C]"         {channel="..."}
	Number    temperature_shadow            "Temperature shadow [%.1f °C]"      {channel="..."}
	Number    temperature_threshold         "Temperature threshold [%.1f °C]"
	Switch    sun_protection_temperature    "Sun protection temperature [%s]    {channel="..."}

	# Rule init:
	habapp_rules.sensors.sun.SensorTempDiff("temperature_sun", "temperature_shadow", "sun_protection_temperature", "temperature_threshold")
	"""

	def __init__(self, name_temperature_1: str, name_temperature_2: str, name_output: str, threshold: str | float, filter_tau: int = 30 * 60, filter_instant_increase: bool = True, filter_instant_decrease: bool = False) -> None:
		"""Init of sun sensor which takes a two temperature values (one in the sun and one in the shadow)

		:param name_temperature_1: name of OpenHAB first temperature item (NumberItem)
		:param name_temperature_2: name of OpenHAB second temperature item (NumberItem)
		:param name_output: name of OpenHAB output item (SwitchItem)
		:param threshold: threshold for the temperature difference which is supposed that sun is shining. Can be given as float value or name of OpenHAB NumberItem
		:param filter_tau: filter constant for the exponential filter. Default is set to 30 minutes
		:param filter_instant_increase: if set to True, increase of input values will not be filtered
		:param filter_instant_decrease: if set to True, decrease of input values will not be filtered
		"""
		name_temperature_diff = f"H_{name_temperature_1}_{name_temperature_2}_diff"
		HABApp.openhab.interface.create_item("Number", name_temperature_diff, name_temperature_diff.replace("_", " "))

		_SensorBase.__init__(self, name_temperature_diff, name_output, threshold, filter_tau, filter_instant_increase, filter_instant_decrease)

		# init items
		self._item_temperature_1 = HABApp.openhab.items.NumberItem.get_item(name_temperature_1)
		self._item_temperature_2 = HABApp.openhab.items.NumberItem.get_item(name_temperature_2)
		self._item_temp_diff = HABApp.openhab.items.NumberItem.get_item(name_temperature_diff)

		# callbacks
		self._item_temperature_1.listen_event(self._cb_temperature, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_temperature_2.listen_event(self._cb_temperature, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _cb_temperature(self, _: HABApp.openhab.events.ItemStateChangedEvent | None):
		"""Callback, which is triggered if a temperature value changed."""
		if all(isinstance(temperature.value, (int, float)) for temperature in (self._item_temperature_1, self._item_temperature_2)):
			self._item_temp_diff.oh_send_command(abs(self._item_temperature_1.value - self._item_temperature_2.value))


class SunPositionFilter(HABApp.Rule):
	"""Rules class to filter a switch state depending on the sun position. This can be used to only close the blinds of a window, if the sun hits the window

	# Items:
	Number    sun_azimuth           "Sun Azimuth [%.1f °]"              {channel="astro..."}
	Number    sun_elevation         "Sun Elevation [%.1f °]"            {channel="astro..."}
	Switch    sun_shining           "Sun is shining [%s]
	Switch    sun_hits_window       "Sun hits window [%s]

	# Rule init:
	position_window = habapp_rules.sensors.sun.SunPositionWindow(40, 120)
	habapp_rules.sensors.sun.SunPositionFilter(position_window, "sun_azimuth", "sun_elevation", "sun_shining", "sun_hits_window")
	"""

	def __init__(self, sun_position_window: SunPositionWindow | list[SunPositionWindow], name_azimuth: str, name_elevation: str, name_input: str, name_output: str):
		"""Init of sun position filter.

		:param sun_position_window: sun position window, where the sun hits the target
		:param name_azimuth: azimuth of the sun
		:param name_elevation: elevation of the sun
		:param name_input: name of OpenHAB input item (SwitchItem)
		:param name_output: name of OpenHAB output item (SwitchItem)
		"""
		# init HABApp Rule
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_output)
		self._position_windows: list[SunPositionWindow] = sun_position_window if isinstance(sun_position_window, list) else [sun_position_window]

		# init items
		self._item_azimuth = HABApp.openhab.items.NumberItem.get_item(name_azimuth)
		self._item_elevation = HABApp.openhab.items.NumberItem.get_item(name_elevation)
		self._item_input = HABApp.openhab.items.SwitchItem.get_item(name_input)
		self._item_output = HABApp.openhab.items.SwitchItem.get_item(name_output)

		# callbacks
		self._item_azimuth.listen_event(self._update_output, HABApp.openhab.events.ItemStateChangedEventFilter())  # listen_event for elevation is not needed because elevation and azimuth is updated together
		self._item_input.listen_event(self._update_output, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._update_output(None)

	def _sun_in_window(self, azimuth: float, elevation: float) -> bool:
		"""Check if the sun is in the 'sun window' where it hits the target.

		:param azimuth: azimuth of the sun
		:param elevation: elevation of the sun
		:return: True if the sun hits the target, else False
		"""
		sun_in_window = False

		if any(window.azimuth_min <= azimuth <= window.azimuth_max and window.elevation_min <= elevation <= window.elevation_max for window in self._position_windows):
			sun_in_window = True

		return sun_in_window

	def _update_output(self, _: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
		"""Callback, which is triggered if the sun position or input changed."""
		azimuth = self._item_azimuth.value
		elevation = self._item_elevation.value

		if azimuth is None or elevation is None:
			self._instance_logger.warning(f"Azimuth or elevation is None -> will set output to input. azimuth = {azimuth} | elevation = {elevation}")
			filter_output = self._item_input.value
		elif self._item_input.value in {"OFF", None}:
			filter_output = "OFF"
		else:
			filter_output = "ON" if self._sun_in_window(azimuth, elevation) else "OFF"

		if filter_output != self._item_output.value:
			self._item_output.oh_send_command(filter_output)
