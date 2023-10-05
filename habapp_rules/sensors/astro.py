"""Rules for astro actions."""
import abc
import logging

import HABApp

import habapp_rules.core.helper

LOGGER = logging.getLogger(__name__)


class _SetNightDayBase(HABApp.Rule):
	"""Base class for set night / day."""

	def __init__(self, name_target: str, name_elevation: str, elevation_threshold: float) -> None:
		"""Init Rule.

		:param name_target: name of OpenHAB switch item which should be set depending on the sun elevation value
		:param name_elevation: name of OpenHAB elevation (NumberItem)
		:param elevation_threshold: Threshold value for elevation.
		"""
		HABApp.Rule.__init__(self)

		self._item_target = HABApp.openhab.items.SwitchItem.get_item(name_target)
		self._item_elevation = HABApp.openhab.items.NumberItem.get_item(name_elevation)
		self._elevation_threshold = elevation_threshold

		self._item_elevation.listen_event(self._set_night, HABApp.openhab.events.ItemStateChangedEventFilter())

		self.run.soon(self._set_night)

	def _set_night(self, _: HABApp.openhab.events.ItemStateChangedEvent | None = None) -> None:
		"""Callback which sets the state to the night item."""
		if self._item_elevation.value is None:
			return
		habapp_rules.core.helper.send_if_different(self._item_target, self._get_target_value())

	@abc.abstractmethod
	def _get_target_value(self) -> str:
		"""Get target value which should be set.

		:return: target value (ON / OFF)
		"""


class SetDay(_SetNightDayBase):
	"""Rule to set / unset day item at dusk / dawn.

		# Items:
		Switch    night_for_shading     "Night for shading"
		Number    elevation             "Sun elevation [%s]"    <sun>     {channel="astro...}

		# Rule init:
		habapp_rules.actors.shading.SetNight("night_for_shading", "elevation")
	"""

	def __init__(self, name_day: str, name_elevation: str, elevation_threshold: float = 0) -> None:
		"""Init Rule.

		:param name_day: name of OpenHAB switch item which should be set to "ON" after dawn and "OFF after dusk
		:param name_elevation: name of OpenHAB elevation (NumberItem)
		:param elevation_threshold: Threshold value for elevation. If the sun elevation is greater than the threshold, the day item will be set to "ON"
		"""
		_SetNightDayBase.__init__(self, name_day, name_elevation, elevation_threshold)

	def _get_target_value(self) -> str:
		"""Get target value which should be set.

		:return: target value (ON / OFF)
		"""
		return "ON" if self._item_elevation.value > self._elevation_threshold else "OFF"


class SetNight(_SetNightDayBase):
	"""Rule to set / unset night item at dusk / dawn.

		# Items:
		Switch    night_for_shading     "Night for shading"
		Number    elevation             "Sun elevation [%s]"    <sun>     {channel="astro...}

		# Rule init:
		habapp_rules.actors.shading.SetNight("night_for_shading", "elevation")
	"""

	def __init__(self, name_night: str, name_elevation: str, elevation_threshold: float = -8) -> None:
		"""Init Rule.

		:param name_night: name of OpenHAB switch item which should be set to "ON" after dusk and "OFF after dawn
		:param name_elevation: name of OpenHAB elevation (NumberItem)
		:param elevation_threshold: Threshold value for elevation. If the sun elevation is below the threshold, the night item will be set to "ON"
		"""
		_SetNightDayBase.__init__(self, name_night, name_elevation, elevation_threshold)

	def _get_target_value(self) -> str:
		"""Get target value which should be set.

		:return: target value (ON / OFF)
		"""
		return "ON" if self._item_elevation.value < self._elevation_threshold else "OFF"
