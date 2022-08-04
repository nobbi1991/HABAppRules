"""Rule manage a light."""
from __future__ import annotations

import dataclasses
import logging
import typing

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.interface
import HABApp.openhab.items
import HABApp.util

import habapp_rules.system
import habapp_rules.actors.state_observer
import habapp_rules.common.helper
import habapp_rules.common.state_machine_rule

LOGGER = logging.getLogger("HABApp.actors.light")
LOGGER.setLevel("DEBUG")

BrightnessTypes = typing.Union[list[typing.Union[float, bool]], float, bool]


@dataclasses.dataclass
class StateConfig:
	"""Class for defining brightness and timeout for a single state."""
	value_day: float | bool
	value_night: float | bool
	value_sleeping: float | bool
	timeout_day: float
	timeout_night: float
	timeout_sleeping: float

	def __post_init__(self) -> None:
		"""Checks after init."""
		for dataset in [(self.value_day, self.timeout_day), (self.value_night, self.timeout_night), (self.value_sleeping, self.timeout_sleeping)]:
			if any(dataset):
				assert all(dataset), f"If timeout is set to zero, also value must be zero/False! {dataset}"

	def __str__(self) -> str:
		"""Get a human-readable representation of the dataclass

		:return: human-readable class representation
		"""
		return \
			f"StateConfig" \
			f"\nday: {self.value_day} | {self.timeout_day}s" \
			f"\nnight: {self.value_night} | {self.timeout_night}s" \
			f"\nsleeping: {self.value_sleeping} | {self.timeout_sleeping}s\n"

	def __repr__(self) -> str:
		"""Get a human-readable representation of the dataclass

		:return: human-readable class representation
		"""
		return self.__str__()


@dataclasses.dataclass
class LightConfig:
	"""Class for defining brightness and timeout configuration for a normal light."""
	on: StateConfig
	pre_off: StateConfig
	leaving: StateConfig
	pre_sleep: StateConfig


# pylint: disable=no-member,too-many-instance-attributes
class Light(habapp_rules.common.state_machine_rule.StateMachineRule):
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
		{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff", "conditions": "_preoff_configured"},
		{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_off", "unless": "_preoff_configured"},
		{"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
		{"trigger": "leaving_started", "source": ["auto_on", "auto_off"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
		{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_off"},
		{"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
		{"trigger": "sleep_started", "source": ["auto_on", "auto_off"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"},
		{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_off"},
		{"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"},
	]

	def __init__(self, name_light: str, control_names: list[str], manual_name: str, presence_state_name: str, sleeping_state_name: str, day_name: str, config: LightConfig) -> None:
		"""Init of Sleep object.

		:param name_light: name of OpenHAB light item (SwitchItem | DimmerItem)
		"""
		self._config = config

		super().__init__()
		print(f"init of {self._item_state.name} | state_item: {self._item_state.name}")

		# init items
		light_item = HABApp.core.Items.get_item(name_light)
		if isinstance(light_item, HABApp.openhab.items.dimmer_item.DimmerItem):
			self._item_light = HABApp.openhab.items.DimmerItem.get_item(name_light)
			self._state_observer = habapp_rules.actors.state_observer.StateObserverDimmer(name_light, self._cb_hand_on, self._cb_hand_off, control_names=control_names)
		elif isinstance(light_item, HABApp.openhab.items.switch_item.SwitchItem):
			self._item_light = HABApp.openhab.items.SwitchItem.get_item(name_light)
			self._state_observer = habapp_rules.actors.state_observer.StateObserverSwitch(name_light, self._cb_hand_on, self._cb_hand_off, control_names=control_names)
		else:
			raise TypeError(f"type: {type(light_item)} is not supported!")

		self._item_manual = HABApp.openhab.items.switch_item.SwitchItem.get_item(manual_name)
		self._item_presence_state = HABApp.openhab.items.string_item.StringItem.get_item(presence_state_name)
		self._item_sleeping_state = HABApp.openhab.items.string_item.StringItem.get_item(sleeping_state_name)
		self._item_day = HABApp.openhab.items.switch_item.SwitchItem.get_item(day_name)

		# init state machine
		self._previous_state = ""
		self.state_machine = habapp_rules.common.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			initial=self._get_initial_state("manual"),
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")

		self._brightness_on_last = 100
		self._timeout_on = 5
		self._timeout_pre_off = 8
		self._timeout_pre_sleep = 6
		self._timeout_leaving = 7
		self._set_timeouts()

		# callbacks
		self._item_manual.listen_event(self._cb_manu, HABApp.openhab.events.ItemStateEventFilter())
		self._item_sleeping_state.listen_event(self._cb_sleeping, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_presence_state.listen_event(self._cb_presence, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_day.listen_event(self._cb_day, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._update_openhab_state()

	def _get_initial_state(self, default_value: str) -> str:
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
			if self._item_presence_state.value in (habapp_rules.system.PresenceState.PRESENCE.value, habapp_rules.system.PresenceState.LEAVING.value) and \
					self._item_sleeping_state.value in (habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value):
				return "auto_presleep"
			return "auto_leaving"
		return "auto_off"

	def _update_openhab_state(self) -> None:
		"""Update OpenHAB state item and other states.

		This should method should be set to "after_state_change" of the state machine.
		"""
		super()._update_openhab_state()
		print(f"State change: {self.state}")

		self._set_brightness()
		self._previous_state = self.state

	def _preoff_configured(self) -> bool:
		"""Check whether pre off is configured for the current day/night/sleep state

		:return: True if pre off is configured
		"""
		return bool(self._timeout_pre_off)

	def _leaving_configured(self) -> bool:
		"""Check whether leaving is configured for the current day/night/sleep state

		:return: True if leaving is configured
		"""
		return bool(self._timeout_leaving)

	def _pre_sleep_configured(self) -> bool:
		"""Check whether pre sleep is configured for the current day/night state

		:return: True if pre sleep is configured
		"""
		return bool(self._timeout_pre_sleep)

	def _set_timeouts(self) -> None:
		"""Set timeouts depending on the current day/night/sleep state."""
		sleeping_active = self._item_sleeping_state.value in (habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)

		if sleeping_active:
			self._timeout_on = self._config.on.timeout_sleeping
			self._timeout_pre_off = self._config.pre_off.timeout_sleeping
			self._timeout_leaving = self._config.leaving.timeout_sleeping

		elif bool(self._item_day):
			self._timeout_on = self._config.on.timeout_day
			self._timeout_pre_off = self._config.pre_off.timeout_day
			self._timeout_leaving = self._config.leaving.timeout_day
			self._timeout_pre_sleep = self._config.pre_sleep.timeout_day
		else:
			self._timeout_on = self._config.on.timeout_night
			self._timeout_pre_off = self._config.pre_off.timeout_night
			self._timeout_leaving = self._config.leaving.timeout_night
			self._timeout_pre_sleep = self._config.pre_sleep.timeout_night

		self.state_machine.states["auto"].states["on"].timeout = self._timeout_on
		self.state_machine.states["auto"].states["preoff"].timeout = self._timeout_pre_off
		self.state_machine.states["auto"].states["leaving"].timeout = self._timeout_leaving
		self.state_machine.states["auto"].states["presleep"].timeout = self._timeout_pre_sleep

	def _set_brightness(self) -> None:
		"""Set brightness to light."""
		target_value = self._get_target_brightness()
		if target_value is None:
			return

		if isinstance(target_value, bool):
			if target_value:
				target_value = "ON"
			else:
				target_value = "OFF"
		print(f"set brightness {target_value}")
		self._state_observer.send_command(target_value)

	# pylint: disable=too-many-branches
	def _get_target_brightness(self) -> typing.Optional[bool, float]:
		"""Get configured brightness for the current day/night/sleep state

		:return: brightness value
		"""
		sleeping_active = self._item_sleeping_state.value in (habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)

		if self.state == "auto_on":
			if self._previous_state == "manual":
				return None
			if self._previous_state == "auto_preoff":
				return self._brightness_on_last
			if sleeping_active:
				return self._config.on.value_sleeping
			if bool(self._item_day):
				return self._config.on.value_day
			return self._config.on.value_night

		if self.state == "auto_preoff":
			self._brightness_on_last = self._state_observer.value

			if sleeping_active:
				brightness = self._config.pre_off.value_sleeping
			elif bool(self._item_day):
				brightness = self._config.pre_off.value_day
			else:
				brightness = self._config.pre_off.value_night

			if self._brightness_on_last / 2 < brightness:
				return self._brightness_on_last
			return brightness

		if self.state == "auto_off":
			return False

		if self.state == "auto_presleep":
			if bool(self._item_day):
				return self._config.pre_sleep.value_day
			return self._config.pre_sleep.value_night

		if self.state == "auto_leaving":
			if sleeping_active:
				return self._config.leaving.value_sleeping
			if bool(self._item_day):
				return self._config.leaving.value_day
			return self._config.leaving.value_night

		return None

	def on_enter_auto_init(self):
		if bool(self._item_light):
			self.state_machine.set_state("auto_on")  # todo timeout is not working!
		else:
			self.state_machine.set_state("auto_off")

	def _cb_hand_on(self, event: HABApp.openhab.events.ItemStateEvent | HABApp.openhab.events.ItemCommandEvent, msg: str) -> None:
		"""Callback, which is triggered by the state observer if a manual ON command was detected.

		:param event: original trigger event
		:param msg: message from state observer
		"""
		print(f"{msg}: {event}")
		self.hand_on()

	def _cb_hand_off(self, event: HABApp.openhab.events.ItemStateEvent | HABApp.openhab.events.ItemCommandEvent, msg: str) -> None:
		"""Callback, which is triggered by the state observer if a manual OFF command was detected.

		:param event: original trigger event
		:param msg: message from state observer
		"""
		self.hand_off()

	def _cb_manu(self, event: HABApp.openhab.events.ItemStateEvent) -> None:
		"""Callback, which is triggered if the manual switch has a state event.

		:param event: trigger event
		"""
		if event.value == "ON":
			self.manual_on()
		else:
			self.manual_off()

	def _cb_day(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the day/night switch has a state event.

		:param event: trigger event
		"""
		self._set_timeouts()

	def _cb_presence(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the presence state has a state event.

		:param event: trigger event
		"""
		self._set_timeouts()
		if event.value == rules.system.PresenceState.LEAVING.value:
			self.leaving_started()
		if event.value == rules.system.PresenceState.PRESENCE.value and self.state == "auto_leaving":
			self.leaving_aborted()  # todo: restore last brightness?

	def _cb_sleeping(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the sleep state has a state event.

		:param event: trigger event
		"""
		self._set_timeouts()
		if event.value == rules.system.SleepState.PRE_SLEEPING.value:
			self.sleep_started()
		if event.value == rules.system.SleepState.POST_SLEEPING.value and self.state == "auto_presleep":
			self.sleep_aborted()  # todo: restore last brightness ??


# class LightExtended(Light):
#
# 	def __init__(self, name_light):
# 		# add additional states
# 		auto_state: dict[str, list] = next(state for state in self.states if state["name"] == "auto")
# 		auto_state["children"].append({"name": "door"})
# 		auto_state["children"].append({"name": "movement"})
# 		auto_state["children"].append({"name": "preoff"})
#
# 		# add additional transitions
# 		self.trans.append({"trigger": "door_opened", "source": "auto_off", "dest": "auto_door"})
# 		self.trans.append({"trigger": "movement_detected", "source": "auto_door", "dest": "auto_movement"})
# 		self.trans.append({"trigger": "door_timeout", "source": "auto_door", "dest": "auto_off"})
# 		self.trans.append({"trigger": "movement_on", "source": "auto_off", "dest": "auto_movement"})
# 		self.trans.append({"trigger": "movement_off", "source": "auto_movement", "dest": "auto_preoff"})
# 		self.trans.append({"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"})
# 		self.trans.append({"trigger": "movement_on", "source": "auto_preoff", "dest": "auto_movement"})
# 		self.trans.append({"trigger": "door_closed", "source": "auto_leaving", "dest": "auto_off"})
#
# 		super().__init__(name_light)


test_config = LightConfig(
	on=StateConfig(True, 80, 40, 5, 5, 10),
	pre_off=StateConfig(30, 30, 0, 7, 4, 0),
	leaving=StateConfig(False, 40, 0, 0, 10, 0),
	pre_sleep=StateConfig(0, 10, 0, 0, 20, 0)
)

# light = Light("I11_01_Sofa", control_names=["I11_01_Sofa_ctr"], manual_name="I999_01_Licht_Sofa_manual", presence_state_name="I999_00_Presence_state", sleeping_state_name="I999_00_Sleeping_state", day_name="I999_00_Day", config=test_config_new)
# light = Light("I11_01_TV", control_names=["I11_01_TV_ctr", "I11_01_TV_Sofa_ctr"], manual_name="I999_01_Licht_Sofa_manual", presence_state_name="I999_00_Presence_state", sleeping_state_name="I999_00_Sleeping_state", day_name="I999_00_Day", config=test_config_new)
# light = Light("I11_01_Schreibtisch", control_names=[], manual_name="I999_01_Licht_Sofa_manual", presence_state_name="I999_00_Presence_state", sleeping_state_name="I999_00_Sleeping_state", day_name="I999_00_Day", config=test_config)

# light_abstell = Light("I11_05_Haupt", control_names=["I11_05_Haupt_ctr"], manual_name="I999_01_Licht_Sofa_manual", presence_state_name="I999_00_Presence_state", sleeping_state_name="I999_00_Sleeping_state", day_name="I999_00_Day", config=test_config)
#
