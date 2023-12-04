"""Light HCL rules."""
import datetime

import HABApp

import habapp_rules.core.helper

EXAMPLE_CONFIG_ELEVATION = [
	(-15, 2600),
	(0, 3500),
	(15, 6500)
]

EXAMPLE_CONFIG_TIME = [
	(0, 2200),
	(4, 2200),
	(5, 3200),
	(6, 3940),
	(8, 5000),
	(12, 7000),
	(19, 7000),
	(21, 5450),
	(22, 4000),
	(23, 2600),
]


class _HclBase(HABApp.Rule):
	"""Base class for HCL rules."""

	def __init__(self, name_color: str, config: list[tuple[float, float]]):
		"""Init base class.

		:param name_color: Name of openHAB color item (NumberItem)
		:param config: config for HCL rule
		"""
		HABApp.Rule.__init__(self)
		self.rule_name += f"_{name_color}"

		self._config = self._get_sorted_config(config)
		self._item_color = HABApp.openhab.items.NumberItem.get_item(name_color)

	@staticmethod
	def _get_sorted_config(config_raw: list[tuple[float, float]]) -> list[tuple[float, float]]:
		"""Get sorted config

		:param config_raw: raw config
		:return: sorted config
		"""
		return sorted(config_raw, key=lambda x: x[0])

	@staticmethod
	def _get_interpolated_value(config_start: tuple[float, float], config_end: tuple[float, float], value: float) -> float:
		"""Get interpolated value

		:param config_start: start config
		:param config_end: end config
		:param value: input value which is the input for the interpolation
		:return: interpolated value
		"""
		fit_m = (config_end[1] - config_start[1]) / (config_end[0] - config_start[0])
		fit_t = config_end[1] - fit_m * config_end[0]

		return fit_m * value + fit_t


class HclElevation(_HclBase):
	"""Sun elevation based HCL."""

	def __init__(self, name_elevation: str, name_color: str, config: list[tuple[float, float]]):
		"""Init sun elevation based HCL rule.

		:param name_elevation: Name of sun elevation openHAB item (NumberItem)
		:param name_color: Name of openHAB color item (NumberItem)
		:param config: config for HCL rule
		"""

		_HclBase.__init__(self, name_color, config)

		self._item_elevation = HABApp.openhab.items.NumberItem.get_item(name_elevation)

		self._item_elevation.listen_event(self._cb_elevation, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._cb_elevation(None)

	def _get_hcl_color(self, elevation: float) -> float:
		"""Get HCL color depending on elevation

		:param elevation: current elevation value
		:return: target light color
		"""
		return_value = 0
		if elevation <= self._config[0][0]:
			return_value = self._config[0][1]

		elif elevation >= self._config[-1][0]:
			return_value = self._config[-1][1]

		else:
			for idx, config_itm in enumerate(self._config):  # pragma: no cover
				if config_itm[0] <= elevation <= self._config[idx + 1][0]:
					return_value = self._get_interpolated_value(config_itm, self._config[idx + 1], elevation)
					break

		return return_value

	def _cb_elevation(self, _: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
		"""Callback which is called if elevation changed"""
		if self._item_elevation.value is not None:
			habapp_rules.core.helper.send_if_different(self._item_color, self._get_hcl_color(self._item_elevation.value))


class HclTime(_HclBase):
	"""Time based HCL."""

	def __init__(self, name_color: str, config: list[tuple[float, float]]):
		"""Init time based HCL rule.

		:param name_color: Name of openHAB color item (NumberItem)
		:param config: config for HCL rule
		"""

		_HclBase.__init__(self, name_color, config)
		self.run.every(None, 300, self._update_color)  # every 5 minutes

	def _get_hcl_color(self) -> float:
		"""Get HCL color depending on time

		:return: target light color
		"""
		current_time = datetime.datetime.now()

		if current_time.hour < self._config[0][0]:
			start_config = (self._config[-1][0] - 24, self._config[-1][1])
			end_config = self._config[0]

		elif current_time.hour >= self._config[-1][0]:
			start_config = self._config[-1]
			end_config = (self._config[0][0] + 24, self._config[0][1])

		else:
			for idx, config_itm in enumerate(self._config):  # pragma: no cover
				if config_itm[0] <= current_time.hour < self._config[idx + 1][0]:
					start_config = config_itm
					end_config = self._config[idx + 1]
					break

		return self._get_interpolated_value(start_config, end_config, current_time.hour + current_time.minute / 60)

	def _update_color(self) -> None:
		"""Callback which is called every 5 minutes"""
		habapp_rules.core.helper.send_if_different(self._item_color, self._get_hcl_color())
