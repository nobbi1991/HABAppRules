"""Rules to handle sun sensors."""
import abc
import dataclasses
import logging

import HABApp

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

	def __init__(self, threshold: str | float, name_output: str) -> None:
		"""Init of base class for sun sensors.

		:param threshold: threshold for the temperature difference which is supposed that sun is shining. Can be given as float value or name of OpenHAB NumberItem
		:param name_output: name of OpenHAB output item (SwitchItem)
		"""
		# init HABApp Rule
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_output)

		# init items
		self._item_output = HABApp.openhab.items.SwitchItem.get_item(name_output)
		self._item_threshold = HABApp.openhab.items.NumberItem.get_item(threshold) if isinstance(threshold, str) else None

		# init hysteresis
		threshold = self._item_threshold.value if self._item_threshold is not None else threshold
		self._hysteresis = habapp_rules.common.hysteresis.HysteresisSwitch(threshold, 1, False)

		# callbacks
		if self._item_threshold:
			self._item_threshold.listen_event(self._cb_threshold, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _send_output(self, new_value: str) -> None:
		"""Send output if different.

		:param new_value: new value which should be sent
		"""

		if new_value != self._item_output.value:
			self._item_output.oh_send_command(new_value)
			self._instance_logger.debug(f"Set output '{self._item_output.name}' to {new_value}")

	def _cb_threshold(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the threshold changed.

		:param event:  trigger event
		"""
		self._hysteresis.set_threshold_on(event.value)
		self._cb_sensor_value(None)

	@abc.abstractmethod
	def _cb_sensor_value(self, event: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
		"""Callback, which is triggered if the sensor value changed.

		:param event: trigger event
		"""


class SensorTempDiff(_SensorBase):
	"""Rules class to set sun protection depending on temperature difference. E.g. temperature in the sun / temperature in the shadow.

	# Items:
	Number    temperature_sun               "Temperature sun [%.1f °C]"         {channel="..."}
	Number    temperature_shadow            "Temperature shadow [%.1f °C]"      {channel="..."}
	Number    temperature_threshold         "Temperature threshold [%.1f °C]"
	Switch    sun_protection_temperature    "Sun protection temperature [%s]    {channel="..."}

	# Rule init:
	habapp_rules.sensors.sun.SensorTempDiff("temperature_sun", "temperature_shadow", "temperature_threshold", "sun_protection_temperature")
	"""

	def __init__(self, name_temperature_1: str, name_temperature_2: str, threshold: str | float, name_output: str) -> None:
		"""Init of sun sensor which takes two temperature values (one in the sun, and one in the shadow).

		:param name_temperature_1: name of OpenHAB temperature item (NumberItem)
		:param name_temperature_2: name of OpenHAB temperature item (NumberItem)
		:param threshold: threshold for the temperature difference which is supposed that sun is shining. Can be given as float value or name of OpenHAB NumberItem
		:param name_output: name of OpenHAB output item (SwitchItem)
		"""
		_SensorBase.__init__(self, threshold, name_output)

		# init items
		self._item_temperature_1 = HABApp.openhab.items.NumberItem.get_item(name_temperature_1)
		self._item_temperature_2 = HABApp.openhab.items.NumberItem.get_item(name_temperature_2)

		# callbacks
		self._item_temperature_1.listen_event(self._cb_sensor_value, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_temperature_2.listen_event(self._cb_sensor_value, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._cb_sensor_value(None)
		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with name '{self.rule_name}' was successful.")

	def _cb_sensor_value(self, event: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
		"""Callback, which is triggered if the sensor value changed.

		:param event: trigger event
		"""
		if self._item_temperature_1.value is None or self._item_temperature_2.value is None:
			self._instance_logger.warning(f"Can not get temperature difference. At least one temperature is None: temperature_1: {self._item_temperature_2.value} | temperature_2: {self._item_temperature_2.value}")
			return

		temp_diff = abs(self._item_temperature_1.value - self._item_temperature_2.value)
		new_output = self._hysteresis.get_output(temp_diff)

		self._send_output(new_output)


class SensorBrightness(_SensorBase):
	"""Rules class to set sun protection depending on brightness level.

	# Items:
	Number    brightness                    "Current brightness [%d lux]"       {channel="..."}
	Number    brightness_threshold          "Brightness threshold [%d lux]"
	Switch    sun_protection_brightness     "Sun protection brightness [%s]     {channel="..."}

	# Rule init:
	habapp_rules.sensors.sun.SensorBrightness("brightness","brightness_threshold", "sun_protection_brightness")
	"""

	def __init__(self, name_brightness: str, name_threshold: str | float, name_output: str) -> None:
		"""Init of sun sensor which takes a brightness value

		:param name_brightness: name of OpenHAB brightness item (NumberItem)
		:param name_threshold: threshold for the temperature difference which is supposed that sun is shining. Can be given as float value or name of OpenHAB NumberItem
		:param name_output: name of OpenHAB output item (SwitchItem)
		"""
		_SensorBase.__init__(self, name_threshold, name_output)

		# init items
		self._item_brightness = HABApp.openhab.items.NumberItem.get_item(name_brightness)

		# callbacks
		self._item_brightness.listen_event(self._cb_sensor_value, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._cb_sensor_value(None)
		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with name '{self.rule_name}' was successful.")

	def _cb_sensor_value(self, event: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
		"""Callback, which is triggered if the brightness changed.

		:param event:  trigger event
		"""
		value = event.value if event else self._item_brightness.value
		self._send_output(self._hysteresis.get_output(value))


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
		self._position_window: list[SunPositionWindow] = sun_position_window if isinstance(sun_position_window, list) else [sun_position_window]

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
		for window in self._position_window:
			if window.azimuth_min <= azimuth <= window.azimuth_max and window.elevation_min <= elevation <= window.elevation_max: # pylint: disable=consider-using-any-or-all
				sun_in_window = True

		return sun_in_window

	def _update_output(self, _: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
		"""Callback, which is triggered if the sun position or input changed."""
		azimuth = self._item_azimuth.value
		elevation = self._item_elevation.value

		if azimuth is None or elevation is None:
			self._instance_logger.warning(f"Azimuth or elevation is None -> will set output to input. azimuth = {azimuth} | elevation = {elevation}")
			filter_output = self._item_input.value
		elif self._item_input.value in ("OFF", None):
			filter_output = "OFF"
		else:
			filter_output = "ON" if self._sun_in_window(azimuth, elevation) else "OFF"

		if filter_output != self._item_output.value:
			self._item_output.oh_send_command(filter_output)
