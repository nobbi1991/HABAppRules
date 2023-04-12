"""Rules for managing movement sensors."""

import logging

import HABApp

import habapp_rules.common.hysteresis
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system.sleep

LOGGER = logging.getLogger(__name__)


# pylint: disable=no-member, too-many-instance-attributes
class Movement(habapp_rules.core.state_machine_rule.StateMachineRule):
	"""Class for filtering movement sensors."""
	# todo: extend sleep lock if movement is active during sleep_lock
	states = [
		{"name": "Locked"},
		{"name": "SleepLocked"},
		{"name": "PostSleepLocked", "timeout": 99, "on_timeout": "timeout_post_sleep_locked"},
		{"name": "Unlocked", "initial": "Init", "children": [
			{"name": "Init"},
			{"name": "Wait"},
			{"name": "Movement"},
			{"name": "MovementExtended", "timeout": 99, "on_timeout": "timeout_movement_extended"},
			{"name": "TooBright"},
		]}
	]

	trans = [
		# lock
		{"trigger": "lock_on", "source": ["Unlocked", "SleepLocked", "PostSleepLocked"], "dest": "Locked"},
		{"trigger": "lock_off", "source": "Locked", "dest": "Unlocked", "unless": "_sleep_active"},
		{"trigger": "lock_off", "source": "Locked", "dest": "SleepLocked", "conditions": "_sleep_active"},

		# sleep
		{"trigger": "sleep_started", "source": "Unlocked", "dest": "SleepLocked"},
		{"trigger": "sleep_end", "source": "SleepLocked", "dest": "Unlocked", "unless": "_post_sleep_lock_active"},
		{"trigger": "sleep_end", "source": "SleepLocked", "dest": "PostSleepLocked", "conditions": "_post_sleep_lock_active"},
		{"trigger": "timeout_post_sleep_locked", "source": "PostSleepLocked", "dest": "Unlocked"},

		# movement
		{"trigger": "movement_on", "source": "Unlocked_Wait", "dest": "Unlocked_Movement"},
		{"trigger": "movement_off", "source": "Unlocked_Movement", "dest": "Unlocked_MovementExtended", "conditions": "_movement_extended_active"},
		{"trigger": "movement_off", "source": "Unlocked_Movement", "dest": "Unlocked_Wait", "unless": "_movement_extended_active"},
		{"trigger": "timeout_movement_extended", "source": "Unlocked_MovementExtended", "dest": "Unlocked_Wait"},
		{"trigger": "movement_on", "source": "Unlocked_MovementExtended", "dest": "Unlocked_Movement"},

		# brightness
		{"trigger": "brightness_over_threshold", "source": "Unlocked_Wait", "dest": "Unlocked_TooBright"},
		{"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Wait", "unless": "_raw_movement_active"},
		{"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Movement", "conditions": "_raw_movement_active"}
	]

	def __init__(self,
	             name_raw: str,
	             name_filtered: str,
	             extended_movement_time: int = 5,
	             name_brightness: str | None = None,
	             brightness_threshold: int | str | None = None,
	             name_lock: str | None = None, name_sleep_state: str | None = None,
	             post_sleep_lock_time: int = 10):
		"""Init of movement filter.

		:param name_raw: name of OpenHAB unfiltered movement item (SwitchItem)
		:param name_filtered: name of OpenHAB filtered movement item (SwitchItem)
		:param extended_movement_time: time in seconds which will extend the movement after movement is off. If it is set to 0 the time will not be extended
		:param name_brightness: name of OpenHAB brightness item (NumberItem)
		:param brightness_threshold: brightness threshold value (float) or name of OpenHAB brightness threshold item (NumberItem)
		:param name_lock: name of OpenHAB lock item (SwitchItem)
		:param name_sleep_state: name of OpenHAB sleep state item (StringItem)
		:param post_sleep_lock_time: Lock time after sleep
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if configuration is not valid
		"""

		if bool(name_brightness) != bool(brightness_threshold):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("'name_brightness' or 'brightness_threshold' is missing!")

		super().__init__(f"H_Movement_{name_raw}_state")
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_raw)
		self._brightness_threshold_value = brightness_threshold if isinstance(brightness_threshold, int) else None
		self._timeout_extended_movement = extended_movement_time
		self._timeout_post_sleep_lock = post_sleep_lock_time
		self.states[2]["timeout"] = self._timeout_post_sleep_lock
		self.states[3]["children"][3]["timeout"] = self._timeout_extended_movement

		# get items
		self._item_movement_raw = HABApp.openhab.items.SwitchItem.get_item(name_raw)
		self._item_movement_filtered = HABApp.openhab.items.SwitchItem.get_item(name_filtered)
		self._item_brightness = HABApp.openhab.items.NumberItem.get_item(name_brightness) if name_brightness else None
		self._item_brightness_threshold = HABApp.openhab.items.NumberItem.get_item(brightness_threshold) if isinstance(brightness_threshold, str) else None
		self._item_lock = HABApp.openhab.items.SwitchItem.get_item(name_lock) if name_lock else None
		self._item_sleep = HABApp.openhab.items.StringItem.get_item(name_sleep_state) if name_sleep_state else None

		self._hysteresis_switch = habapp_rules.common.hysteresis.HysteresisSwitch(threshold_value := self._get_brightness_threshold(), threshold_value * 0.1) if name_brightness else None

		# init state machine
		self._previous_state = None
		self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")
		self._set_initial_state()

		# register callbacks
		self._item_movement_raw.listen_event(self._cb_movement_raw, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_brightness is not None:
			self._item_brightness.listen_event(self._cb_brightness, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_brightness_threshold is not None:
			self._item_brightness_threshold.listen_event(self._cb_threshold_change, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_lock is not None:
			self._item_lock.listen_event(self._cb_lock, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_sleep is not None:
			self._item_sleep.listen_event(self._cb_sleep, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._instance_logger.info(f"init of {self.__class__.__name__} '{name_raw}' with state_item = {self._item_state.name} was successful.")

	def _get_initial_state(self, default_value: str = "initial") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		if self._item_lock:
			return "Locked"
		if self._item_sleep and self._item_sleep.value == habapp_rules.system.SleepState.SLEEPING.value:
			return "SleepLocked"
		if self._item_brightness and self._hysteresis_switch.get_output(self._item_brightness.value):
			return "Unlocked_TooBright"
		if self._item_movement_raw:
			return "Unlocked_Movement"
		return "Unlocked_Wait"

	def _update_openhab_state(self):
		"""Update OpenHAB state item. This should method should be set to "after_state_change" of the state machine."""
		if self.state != self._previous_state:
			super()._update_openhab_state()
			self.__send_filtered_movement()

			self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")
			self._previous_state = self.state

	def __send_filtered_movement(self) -> None:
		"""Send filtered movement state to OpenHAB item."""
		target_state = "ON" if self.state in {"Unlocked_Movement", "Unlocked_MovementExtended"} else "OFF"
		self._item_movement_filtered.oh_post_update_if(target_state, not_equal=target_state)  # todo: check if working as expected

	def _raw_movement_active(self) -> bool:
		"""Check if raw movement is active

		:return: True if active, else False
		"""
		return bool(self._item_movement_raw)

	def _movement_extended_active(self) -> bool:
		"""Check if extended movement is active

		:return: True if active, else False
		"""
		return self._timeout_extended_movement > 0

	def _post_sleep_lock_active(self) -> bool:
		"""Check if post sleep lock is active

		:return: True if active, else False
		"""
		return self._timeout_post_sleep_lock > 0

	def _sleep_active(self) -> bool:
		"""Check if sleeping is active

		:return: True if sleeping is active, else False
		"""
		return self._item_sleep.value == habapp_rules.system.SleepState.SLEEPING.value

	def _get_brightness_threshold(self) -> int:
		"""Get the current brightness threshold value.
		
		:return: brightness threshold
		:raises habapp_rules.core.exceptions.HabAppRulesException: if brightness value not given by item or value
		"""
		if self._brightness_threshold_value:
			return self._brightness_threshold_value
		if self._item_brightness_threshold is not None:
			return self._item_brightness_threshold.value
		raise habapp_rules.core.exceptions.HabAppRulesException(f"Can not get brightness threshold. Brightness value or item is not given. value: {self._brightness_threshold_value} | item: {self._item_brightness}")

	# pylint: disable=invalid-name
	def on_enter_Unlocked_Init(self):
		"""Callback, which is called on enter of Unlocked_Init state"""
		if self._item_brightness and self._hysteresis_switch.get_output(self._item_brightness.value):
			self.to_Unlocked_TooBright()
		elif self._item_movement_raw:
			self.to_Unlocked_Movement()
		else:
			self.to_Unlocked_Wait()

	def _check_brightness(self, value: float | None = None) -> None:
		"""Check if brightness is higher than the threshold and trigger the class methods.

		:param value: Value to check. None if last value should be used
		"""
		if self._hysteresis_switch.get_output(value):
			self.brightness_over_threshold()
		else:
			self.brightness_below_threshold()

	def _cb_threshold_change(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the brightness threshold state changed.

		:param event: trigger event
		"""
		self._hysteresis_switch.set_threshold_on(event.value)
		self._check_brightness()

	def _cb_movement_raw(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the raw movement state changed.

		:param event: trigger event
		"""
		if event.value == "ON":
			self.movement_on()
		else:
			self.movement_off()

	def _cb_brightness(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the brightness state changed.

		:param event: trigger event
		"""
		self._check_brightness(event.value)

	def _cb_lock(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the lock state changed.

		:param event: trigger event
		"""
		if event.value == "ON":
			self.lock_on()
		else:
			self.lock_off()

	def _cb_sleep(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the sleep state changed.

		:param event: trigger event
		"""
		if event.value == habapp_rules.system.SleepState.SLEEPING.value:
			self.sleep_started()
		if event.value == habapp_rules.system.SleepState.AWAKE.value:
			self.sleep_end()
