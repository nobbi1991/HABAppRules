"""Rule manage a light."""
from __future__ import annotations

import logging
import math
import typing

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.interface
import HABApp.openhab.items
import HABApp.util

import habapp_rules.actors.light_config
import habapp_rules.actors.state_observer
import habapp_rules.core.helper
import habapp_rules.core.state_machine_rule
import habapp_rules.core.logger
import habapp_rules.system

LOGGER = logging.getLogger(__name__)

BrightnessTypes = typing.Union[list[typing.Union[float, bool]], float, bool]


# todo check what happens if timeout value changes. e.g. day to night change and timeout_day = 100 and timeout_night = 5: will the day timeout finish or will it take the night timeout?!
# todo: test switch on at night. there is one cb_brightness_change which should not be there!


# pylint: disable=no-member,too-many-instance-attributes
class Light(habapp_rules.core.state_machine_rule.StateMachineRule):
	"""Rules class to manage sleep state."""

	states = [
		{"name": "manual"},
		{"name": "auto", "initial": "init", "children": [
			{"name": "init"},
			{"name": "on", "timeout": 10, "on_timeout": "auto_on_timeout"},
			{"name": "preoff", "timeout": 4, "on_timeout": "preoff_timeout"},
			{"name": "off"},
			{"name": "leaving", "timeout": 5, "on_timeout": "leaving_timeout"},
			{"name": "presleep", "timeout": 5, "on_timeout": "presleep_timeout"},
		]}
	]

	trans = [
		{"trigger": "manual_on", "source": "auto", "dest": "manual"},
		{"trigger": "manual_off", "source": "manual", "dest": "auto"},
		{"trigger": "hand_on", "source": ["auto_off", "auto_preoff"], "dest": "auto_on"},
		{"trigger": "hand_off", "source": ["auto_on", "auto_leaving", "auto_presleep"], "dest": "auto_off"},
		{"trigger": "hand_off", "source": "auto_preoff", "dest": "auto_on"},
		{"trigger": "hand_changed", "source": "auto_on", "dest": "auto_on"},
		{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
		{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_off", "unless": "_pre_off_configured"},
		{"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
		{"trigger": "leaving_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
		{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_on", "conditions": "_was_on_before"},
		{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_off", "unless": "_was_on_before"},
		{"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
		{"trigger": "sleep_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"},
		{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_on", "conditions": "_was_on_before"},
		{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_off", "unless": "_was_on_before"},
		{"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"},
	]

	def __init__(self, name_light: str, control_names: list[str], manual_name: str, presence_state_name: str, sleeping_state_name: str, day_name: str, config: habapp_rules.actors.light_config.LightConfig) -> None:
		"""Init of Sleep object.

		:param name_light: name of OpenHAB light item (SwitchItem | DimmerItem)
		:param control_names: names of OpenHab items which must be configured as control (-ctr) items. This can be used for KNX items to detect increase / decrease commands from physical wall controllers
		:param manual_name: name of OpenHAB switch item to disable all automatic functions
		:param presence_state_name: name of OpenHAB presence state item
		:param sleeping_state_name: name of OpenHAB sleeping state item
		:param day_name: name of OpenHAB switch item which is 'ON' during day and 'OFF' during night
		:param config: configuration of the light object
		:raises TypeError: if type of light_item is not supported
		"""
		self._config = config

		super().__init__(f"H{name_light}_state")
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_light)

		# init items
		light_item = HABApp.core.Items.get_item(name_light)
		if isinstance(light_item, HABApp.openhab.items.dimmer_item.DimmerItem):
			self._item_light = HABApp.openhab.items.DimmerItem.get_item(name_light)
			self._state_observer = habapp_rules.actors.state_observer.StateObserverDimmer(name_light, self._cb_hand_on, self._cb_hand_off, self._cb_hand_changed, control_names=control_names)
		else:
			raise TypeError(f"type: {type(light_item)} is not supported!")

		self._item_manual = HABApp.openhab.items.switch_item.SwitchItem.get_item(manual_name)
		self._item_presence_state = HABApp.openhab.items.string_item.StringItem.get_item(presence_state_name)
		self._item_sleeping_state = HABApp.openhab.items.string_item.StringItem.get_item(sleeping_state_name)
		self._item_day = HABApp.openhab.items.switch_item.SwitchItem.get_item(day_name)

		# init state machine
		self._previous_state = None
		self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")

		self._brightness_before = -1
		self._timeout_on = 0
		self._timeout_pre_off = 0
		self._timeout_pre_sleep = 0
		self._timeout_leaving = 0
		self._set_timeouts()
		self._set_initial_state()

		# callbacks
		self._item_manual.listen_event(self._cb_manu, HABApp.openhab.events.ItemStateEventFilter())
		self._item_sleeping_state.listen_event(self._cb_sleeping, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_presence_state.listen_event(self._cb_presence, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_day.listen_event(self._cb_day, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._update_openhab_state()
		self._instance_logger.info(f"init of light {self._item_light.name}  with state_item = {self._item_state.name} was successful.")

	def _get_initial_state(self, default_value: str = "") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		if bool(self._item_manual):
			return "manual"
		if bool(self._item_light):
			if self._item_presence_state.value == habapp_rules.system.PresenceState.PRESENCE.value and \
					self._item_sleeping_state.value in (habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.SleepState.LOCKED.value):
				return "auto_on"
			if self._pre_sleep_configured() and \
					self._item_presence_state.value in (habapp_rules.system.PresenceState.PRESENCE.value, habapp_rules.system.PresenceState.LEAVING.value) and \
					self._item_sleeping_state.value in (habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value):
				return "auto_presleep"
			if self._leaving_configured():
				return "auto_leaving"
			return "auto_on"
		return "auto_off"

	def _set_initial_state(self) -> None:
		"""Set initial state.

		if the ``initial_state`` parameter of the state machine constructor is used the timeouts will not be started for the initial state.
		"""
		initial_state = self._get_initial_state()
		eval(f"self.to_{initial_state}()")  # pylint: disable=eval-used

	def _update_openhab_state(self) -> None:
		"""Update OpenHAB state item and other states.

		This should method should be set to "after_state_change" of the state machine.
		"""
		if self.state != self._previous_state:
			super()._update_openhab_state()
			self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

			self._set_brightness()
			self._previous_state = self.state

	def _pre_off_configured(self) -> bool:
		"""Check whether pre-off is configured for the current day/night/sleep state

		:return: True if pre-off is configured
		"""
		return bool(self._timeout_pre_off)

	def _leaving_configured(self) -> bool:
		"""Check whether leaving is configured for the current day/night/sleep state

		:return: True if leaving is configured
		"""
		return bool(self._timeout_leaving)

	def _pre_sleep_configured(self) -> bool:
		"""Check whether pre-sleep is configured for the current day/night state

		:return: True if pre-sleep is configured
		"""
		pre_sleep_prevent = False
		if self._config.pre_sleep_prevent:
			if callable(self._config.pre_sleep_prevent):
				pre_sleep_prevent = self._config.pre_sleep_prevent()
			if isinstance(self._config.pre_sleep_prevent, HABApp.openhab.items.OpenhabItem):
				pre_sleep_prevent = bool(self._config.pre_sleep_prevent)

		return bool(self._timeout_pre_sleep) and not pre_sleep_prevent

	def _was_on_before(self) -> bool:
		"""Check whether the dimmer was on before

		:return: True if the dimmer was on before, else False
		"""
		return bool(self._brightness_before)

	def _set_timeouts(self) -> None:
		"""Set timeouts depending on the current day/night/sleep state."""
		sleeping_active = self._item_sleeping_state.value == habapp_rules.system.SleepState.SLEEPING.value

		if sleeping_active:
			self._timeout_on = self._config.on.sleeping.timeout
			self._timeout_pre_off = getattr(self._config.pre_off.sleeping if self._config.pre_off else None, "timeout", None)
			self._timeout_leaving = getattr(self._config.leaving.sleeping if self._config.leaving else None, "timeout", None)
			self._timeout_pre_sleep = None

		elif bool(self._item_day):
			self._timeout_on = self._config.on.day.timeout
			self._timeout_pre_off = getattr(self._config.pre_off.day if self._config.pre_off else None, "timeout", None)
			self._timeout_leaving = getattr(self._config.leaving.day if self._config.leaving else None, "timeout", None)
			self._timeout_pre_sleep = getattr(self._config.pre_sleep.day if self._config.pre_sleep else None, "timeout", None)
		else:
			self._timeout_on = self._config.on.night.timeout
			self._timeout_pre_off = getattr(self._config.pre_off.night if self._config.pre_off else None, "timeout", None)
			self._timeout_leaving = getattr(self._config.leaving.night if self._config.leaving else None, "timeout", None)
			self._timeout_pre_sleep = getattr(self._config.pre_sleep.night if self._config.pre_sleep else None, "timeout", None)

		self.state_machine.states["auto"].states["on"].timeout = self._timeout_on
		self.state_machine.states["auto"].states["preoff"].timeout = self._timeout_pre_off
		self.state_machine.states["auto"].states["leaving"].timeout = self._timeout_leaving
		self.state_machine.states["auto"].states["presleep"].timeout = self._timeout_pre_sleep

	def _set_brightness(self) -> None:
		"""Set brightness to light."""
		target_value = self._get_target_brightness()
		if target_value is None or self._previous_state is None:
			# don't change value if target_value is None or _set_brightness will be called during init (_previous_state == None)
			return

		if isinstance(target_value, bool):
			if target_value:
				target_value = "ON"
			else:
				target_value = "OFF"
		self._instance_logger.debug(f"set brightness {target_value}")
		self._state_observer.send_command(target_value)

	# pylint: disable=too-many-branches, too-many-return-statements
	def _get_target_brightness(self) -> typing.Optional[bool, float]:
		"""Get configured brightness for the current day/night/sleep state

		:return: brightness value
		"""
		sleeping_active = self._item_sleeping_state.value in (habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)

		if self.state == "auto_on":
			if self._previous_state == "manual":
				return None
			if self._previous_state == "auto_off" and self._state_observer.last_manual_event.value not in {"ON", 100.0}:
				return None
			if self._previous_state in {"auto_preoff", "auto_leaving", "auto_presleep"}:
				return self._brightness_before
			if sleeping_active:
				return self._config.on.sleeping.brightness
			if bool(self._item_day):
				return self._config.on.day.brightness
			return self._config.on.night.brightness

		if self.state == "auto_preoff":
			self._brightness_before = self._state_observer.value

			if sleeping_active:
				brightness_from_config = getattr(self._config.pre_off.sleeping if self._config.pre_off else None, "brightness", None)
			elif bool(self._item_day):
				brightness_from_config = getattr(self._config.pre_off.day if self._config.pre_off else None, "brightness", None)
			else:
				brightness_from_config = getattr(self._config.pre_off.night if self._config.pre_off else None, "brightness", None)

			if brightness_from_config is None:
				return None

			if isinstance(self._state_observer.value, (float, int)) and brightness_from_config > self._state_observer.value:
				return math.ceil(self._state_observer.value / 2)
			return brightness_from_config

		if self.state == "auto_off":
			return False

		if self.state == "auto_presleep":
			if bool(self._item_day):
				return getattr(self._config.pre_sleep.day if self._config.pre_sleep else None, "brightness", None)
			return getattr(self._config.pre_sleep.night if self._config.pre_sleep else None, "brightness", None)

		if self.state == "auto_leaving":
			if sleeping_active:
				return getattr(self._config.leaving.sleeping if self._config.leaving else None, "brightness", None)
			if bool(self._item_day):
				return getattr(self._config.leaving.day if self._config.leaving else None, "brightness", None)
			return getattr(self._config.leaving.night if self._config.leaving else None, "brightness", None)

		return None

	def on_enter_auto_init(self):
		"""Callback, which is called on enter of init state"""
		if bool(self._item_light):
			self.to_auto_on()
		else:
			self.to_auto_off()

	def _cb_hand_on(self, event: HABApp.openhab.events.ItemStateEvent | HABApp.openhab.events.ItemCommandEvent, msg: str) -> None:
		"""Callback, which is triggered by the state observer if a manual ON command was detected.

		:param event: original trigger event
		:param msg: message from state observer
		"""
		self.hand_on()

	def _cb_hand_off(self, event: HABApp.openhab.events.ItemStateEvent | HABApp.openhab.events.ItemCommandEvent, msg: str) -> None:
		"""Callback, which is triggered by the state observer if a manual OFF command was detected.

		:param event: original trigger event
		:param msg: message from state observer
		"""
		self.hand_off()

	def _cb_hand_changed(self, event: HABApp.openhab.events.ItemStateEvent | HABApp.openhab.events.ItemCommandEvent, msg: str) -> None:
		"""Callback, which is triggered by the state observer if a manual OFF command was detected.

		:param event: original trigger event
		:param msg: message from state observer
		"""
		self.hand_changed()

	def _cb_manu(self, event: HABApp.openhab.events.ItemStateEvent) -> None:
		"""Callback, which is triggered if the manual switch has a state event.

		:param event: trigger event
		"""
		if event.value == "ON":
			self.manual_on()
		else:
			self.manual_off()

	def _cb_day(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the day/night switch has a state change event.

		:param event: trigger event
		"""
		self._set_timeouts()

	def _cb_presence(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the presence state has a state change event.

		:param event: trigger event
		"""
		self._set_timeouts()
		if event.value == habapp_rules.system.PresenceState.LEAVING.value:
			self._brightness_before = self._state_observer.value
			self.leaving_started()
		elif event.value == habapp_rules.system.PresenceState.PRESENCE.value and self.state == "auto_leaving":
			self.leaving_aborted()

	def _cb_sleeping(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the sleep state has a state change event.

		:param event: trigger event
		"""
		self._set_timeouts()
		if event.value == habapp_rules.system.SleepState.PRE_SLEEPING.value:
			self._brightness_before = self._state_observer.value
			self.sleep_started()
		elif event.value == habapp_rules.system.SleepState.AWAKE.value and self.state == "auto_presleep":
			self.sleep_aborted()
