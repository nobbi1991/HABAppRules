"""Tests for power rules."""
import HABApp

import habapp_rules.actors.config.power
import habapp_rules.core.helper


class CurrentSwitch(HABApp.Rule):
	"""Rules class to manage basic light states.

	# Items:
	Number    Current              "Current"
	Switch    Something_is_ON      "Something is ON"

	# Config:
	config = habapp_rules.actors.config.power.CurrentSwitchConfig(
		items = habapp_rules.actors.config.light.CurrentSwitchItems(
			current="Current",
			switch="Something_is_ON"
		)
	)

	# Rule init:
	habapp_rules.actors.power.CurrentSwitch(config)
	"""

	def __init__(self, config: habapp_rules.actors.config.power.CurrentSwitchConfig) -> None:
		"""Init current switch rule.

		:param config: config for current switch rule
		"""
		HABApp.Rule.__init__(self)
		self._config = config

		self._check_current_and_set_switch(self._config.items.current.value)
		self._config.items.current.listen_event(self._cb_current_changed, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _check_current_and_set_switch(self, current: float | None) -> None:
		"""Check if current is above the threshold and set switch.

		:param current: current value which should be checked
		"""
		if current is None:
			return
		target_value = "ON" if current > self._config.parameter.threshold else "OFF"
		habapp_rules.core.helper.send_if_different(self._config.items.switch, target_value)

	def _cb_current_changed(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is called if the current value changed.

		:param event: event, which triggered this callback
		"""
		self._check_current_and_set_switch(event.value)
