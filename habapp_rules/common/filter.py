"""Module for filter functions / rules."""
import logging

import HABApp

import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class ExponentialFilter(HABApp.Rule):
	"""Rules class to apply a exponential filter to a number value.

	# Items:
	Number    BrightnessValue                       "Brightness Value [%d]"                         {channel="..."}
	Number    BrightnessFiltered                    "Brightness filtered [%d]"
	Number    BrightnessFilteredInstantIncrease     "Brightness filtered instant increase [%d]"

	# Rule init:
	habapp_rules.common.filter.ExponentialFilter("BrightnessValue", "BrightnessFiltered", 60)  # filter constant 1 minute
    habapp_rules.common.filter.ExponentialFilter("BrightnessValue", "BrightnessFilteredInstantIncrease", 600, True)  # filter constant 10 minutes + instant increase
	"""

	def __init__(self, name_raw: str, name_filtered: str, tau: int, instant_increase: bool = False, instant_decrease: bool = False):
		"""Init exponential filter rule.

		:param name_raw: name of raw OpenHAB item (NumberItem)
		:param name_filtered: name of filtered OpenHAB item (NumberItem)
		:param tau: filter time constant in seconds. E.g. step from 0 to 1 | tau = 5 seconds -> after 5 seconds the value will be 0,67
		:param instant_increase: if set to True, increase of input values will not be filtered
		:param instant_decrease: if set to True, decrease of input values will not be filtered
		"""
		HABApp.Rule.__init__(self)

		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self.rule_name)

		if instant_decrease and instant_decrease:
			self._instance_logger.warning("instant_increase and instant_decrease was set to True. This deactivates the filter completely!")

		self._instant_increase = instant_increase
		self._instant_decrease = instant_decrease

		self._item_raw = HABApp.openhab.items.NumberItem.get_item(name_raw)
		self._item_filtered = HABApp.openhab.items.NumberItem.get_item(name_filtered)

		self._previous_value = self._item_raw.value

		sample_time = tau / 5  # fifth part of the filter time constant
		self._alpha = 0.2  # always 0.2 since we always have the fifth part of the filter time constant
		self.run.every(None, sample_time, self._cb_cyclic_calculate_and_update_output)

		if self._instant_increase or self._instant_decrease:
			self._item_raw.listen_event(self._cb_item_raw, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._instance_logger.debug(f"Successfully created exponential filter for item {self._item_raw.name}")

	def _cb_cyclic_calculate_and_update_output(self) -> None:
		"""Calculate the new filter output and update the filtered item. This must be called cyclic"""
		new_value = self._item_raw.value

		if any(not isinstance(value, (int, float)) for value in (self._previous_value, new_value)):
			self._instance_logger.warning(f"New or previous value is not a number: new_value: {new_value} | previous_value: {self._previous_value}")
			return

		self._send_output(filtered_value := self._alpha * new_value + (1 - self._alpha) * self._previous_value)
		self._previous_value = filtered_value

	def _cb_item_raw(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is called if the value of the raw item changed.

		:param event: event which triggered this event
		"""
		if self._previous_value is None or self._instant_increase and event.value > self._previous_value or self._instant_decrease and event.value < self._previous_value:
			self._send_output(event.value)
			self._previous_value = event.value

	def _send_output(self, new_value: float) -> None:
		"""Send output to the OpenHAB item.

		:param new_value: new value which should be sent
		"""
		self._item_filtered.oh_send_command(new_value)
