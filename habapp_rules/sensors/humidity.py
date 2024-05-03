"""Rule for evaluating a humidity sensor."""
import logging

import HABApp

import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule

LOGGER = logging.getLogger(__name__)


# pylint: disable=no-member
class HumiditySwitch(habapp_rules.core.state_machine_rule.StateMachineRule):
	"""Rule for setting humidity switch if high humidity or a high humidity change is detected."""

	states = [
		{"name": "off"},
		{"name": "on", "initial": "HighHumidity", "children": [
			{"name": "HighHumidity"},
			{"name": "Extended", "timeout": 99, "on_timeout": "on_extended_timeout"},
		]}
	]

	trans = [
		{"trigger": "high_humidity_start", "source": "off", "dest": "on"},
		{"trigger": "high_humidity_start", "source": "on_Extended", "dest": "on_HighHumidity"},
		{"trigger": "high_humidity_end", "source": "on_HighHumidity", "dest": "on_Extended"},
		{"trigger": "on_extended_timeout", "source": "on_Extended", "dest": "off"},
	]

	def __init__(self,
	             name_humidity: str,
	             name_switch: str,
	             absolute_threshold: float = 65,
	             extended_time: int = 10 * 60,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init humidity rule.

		:param name_humidity: Name of OpenHAB NumberItem which holds the humidity
		:param name_switch: Name of OpenHab SwitchItem which will be switched on if high humidity is detected
		:param absolute_threshold: Threshold for high humidity
		:param extended_time: Extended time if humidity is below threshold
		:param name_state: name of the item to hold the state
		:param state_label: OpenHAB label of the state_item; This will be used if the state_item will be created by HABApp
		"""
		self._absolute_threshold = absolute_threshold

		if not name_state:
			name_state = f"H_{name_switch}_state"
		habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, name_state, state_label)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_humidity)

		# get items
		self._item_humidity = HABApp.openhab.items.NumberItem.get_item(name_humidity)
		self._item_output_switch = HABApp.openhab.items.SwitchItem.get_item(name_switch)

		# init state machine
		self._previous_state = None
		self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")
		self._set_initial_state()

		self.state_machine.get_state("on_Extended").timeout = extended_time

		# register callbacks
		self._item_humidity.listen_event(self._cb_humidity, HABApp.openhab.events.ItemStateUpdatedEventFilter())

	def _get_initial_state(self, default_value: str = "initial") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		return "on" if self._check_high_humidity() else "off"

	def _check_high_humidity(self, humidity_value: float | None = None) -> bool:
		"""Check if humidity is above threshold.
		
		:param humidity_value: humidity value, which should be checked. If None, the value of the humidity item will be used
		:return: True if humidity is above threshold
		"""
		if humidity_value is None:
			if self._item_humidity.value is None:
				return False
			humidity_value = self._item_humidity.value

		return humidity_value >= self._absolute_threshold

	def _cb_humidity(self, event: HABApp.openhab.events.ItemStateUpdatedEvent) -> None:
		"""Callback, which is triggered if the humidity was updated.

		:param event: trigger event
		"""
		if self._check_high_humidity(event.value):
			self.high_humidity_start()
		else:
			self.high_humidity_end()
