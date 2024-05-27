"""Module for filter functions / rules."""
import logging

import HABApp

import habapp_rules.common.config.filter
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

	def __init__(self, config: habapp_rules.common.config.filter.ExponentialFilterConfig):
		"""Init exponential filter rule.

		:param config: Config for exponential filter
		"""
		HABApp.Rule.__init__(self)
		self._config = config

		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self.rule_name)

		self._previous_value = self._config.items.raw.value

		sample_time = self._config.parameter.tau / 5  # fifth part of the filter time constant
		self._alpha = 0.2  # always 0.2 since we always have the fifth part of the filter time constant
		self.run.every(None, sample_time, self._cb_cyclic_calculate_and_update_output)

		if self._config.parameter.instant_increase or self._config.parameter.instant_decrease:
			self._config.items.raw.listen_event(self._cb_item_raw, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._instance_logger.debug(f"Successfully created exponential filter for item {self._config.items.raw.name}")

	def _cb_cyclic_calculate_and_update_output(self) -> None:
		"""Calculate the new filter output and update the filtered item. This must be called cyclic"""
		new_value = self._config.items.raw.value

		if any(not isinstance(value, (int, float)) for value in (self._previous_value, new_value)):
			self._instance_logger.warning(f"New or previous value is not a number: new_value: {new_value} | previous_value: {self._previous_value}")
			return

		self._send_output(filtered_value := self._alpha * new_value + (1 - self._alpha) * self._previous_value)
		self._previous_value = filtered_value

	def _cb_item_raw(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is called if the value of the raw item changed.

		:param event: event which triggered this event
		"""
		if self._previous_value is None or self._config.parameter.instant_increase and event.value > self._previous_value or self._config.parameter.instant_decrease and event.value < self._previous_value:
			self._send_output(event.value)
			self._previous_value = event.value

	def _send_output(self, new_value: float) -> None:
		"""Send output to the OpenHAB item.

		:param new_value: new value which should be sent
		"""
		self._config.items.filtered.oh_send_command(new_value)
