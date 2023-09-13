"""Rules to manage lights."""
from __future__ import annotations

import abc
import copy
import logging
import math
import threading
import time
import typing

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.items
import HABApp.util

import habapp_rules.actors.config.light
import habapp_rules.actors.state_observer
import habapp_rules.core.exceptions
import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system

LOGGER = logging.getLogger(__name__)

BrightnessTypes = typing.Union[list[typing.Union[float, bool]], float, bool]


# pylint: disable=no-member, too-many-instance-attributes
class _LightBase(habapp_rules.core.state_machine_rule.StateMachineRule, metaclass=abc.ABCMeta):
	"""Base class for lights."""
	states = [
		{"name": "manual"},
		{"name": "auto", "initial": "init", "children": [
			{"name": "init"},
			{"name": "on", "timeout": 10, "on_timeout": "auto_on_timeout"},
			{"name": "preoff", "timeout": 4, "on_timeout": "preoff_timeout"},
			{"name": "off"},
			{"name": "leaving", "timeout": 5, "on_timeout": "leaving_timeout"},
			{"name": "presleep", "timeout": 5, "on_timeout": "presleep_timeout"},
			{"name": "restoreState"}
		]}
	]

	trans = [
		{"trigger": "manual_on", "source": "auto", "dest": "manual"},
		{"trigger": "manual_off", "source": "manual", "dest": "auto"},
		{"trigger": "hand_on", "source": ["auto_off", "auto_preoff"], "dest": "auto_on"},
		{"trigger": "hand_off", "source": ["auto_on", "auto_leaving", "auto_presleep"], "dest": "auto_off"},
		{"trigger": "hand_off", "source": "auto_preoff", "dest": "auto_on"},
		{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff", "conditions": "_pre_off_configured"},
		{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_off", "unless": "_pre_off_configured"},
		{"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
		{"trigger": "leaving_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_leaving", "conditions": "_leaving_configured"},
		{"trigger": "leaving_aborted", "source": "auto_leaving", "dest": "auto_restoreState"},
		{"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
		{"trigger": "sleep_started", "source": ["auto_on", "auto_off", "auto_preoff"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"},
		{"trigger": "sleep_aborted", "source": "auto_presleep", "dest": "auto_restoreState"},
		{"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"},
	]
	_item_light: HABApp.openhab.items.switch_item.SwitchItem | HABApp.openhab.items.dimmer_item.DimmerItem
	_state_observer: habapp_rules.actors.state_observer.StateObserverSwitch | habapp_rules.actors.state_observer.StateObserverDimmer

	def __init__(self,
	             name_light: str,
	             manual_name: str,
	             presence_state_name: str,
	             day_name: str,
	             config: habapp_rules.actors.config.light.LightConfig,
	             sleeping_state_name: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of basic light object.

		:param name_light: name of OpenHAB light item (SwitchItem | DimmerItem)
		:param manual_name: name of OpenHAB switch item to disable all automatic functions
		:param presence_state_name: name of OpenHAB presence state item
		:param day_name: name of OpenHAB switch item which is 'ON' during day and 'OFF' during night
		:param config: configuration of the light object
		:param sleeping_state_name: [optional] name of OpenHAB sleeping state item
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		:raises TypeError: if type of light_item is not supported
		"""
		self._config = config

		if not name_state:
			name_state = f"H_{name_light}_state"
		habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, name_state, state_label)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_light)

		# init items
		self._item_manual = HABApp.openhab.items.switch_item.SwitchItem.get_item(manual_name)
		self._item_presence_state = HABApp.openhab.items.string_item.StringItem.get_item(presence_state_name)
		self._item_sleeping_state = HABApp.openhab.items.string_item.StringItem.get_item(sleeping_state_name) if sleeping_state_name else None
		self._item_day = HABApp.openhab.items.switch_item.SwitchItem.get_item(day_name)

		# init state machine
		self._previous_state = None
		self._restore_state = None
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
		self._item_manual.listen_event(self._cb_manu, HABApp.openhab.events.ItemStateUpdatedEventFilter())
		if self._item_sleeping_state is not None:
			self._item_sleeping_state.listen_event(self._cb_sleeping, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_presence_state.listen_event(self._cb_presence, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_day.listen_event(self._cb_day, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._update_openhab_state()
		self._instance_logger.debug(super().get_initial_log_message())

	def _get_initial_state(self, default_value: str = "") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		if bool(self._item_manual):
			return "manual"
		if bool(self._item_light):
			if self._item_presence_state.value == habapp_rules.system.PresenceState.PRESENCE.value and \
					getattr(self._item_sleeping_state, "value", "awake") in (habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.SleepState.LOCKED.value):
				return "auto_on"
			if self._pre_sleep_configured() and \
					self._item_presence_state.value in (habapp_rules.system.PresenceState.PRESENCE.value, habapp_rules.system.PresenceState.LEAVING.value) and \
					getattr(self._item_sleeping_state, "value", "") in (habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value):
				return "auto_presleep"
			if self._leaving_configured():
				return "auto_leaving"
			return "auto_on"
		return "auto_off"

	def _update_openhab_state(self) -> None:
		"""Update OpenHAB state item and other states.

		This should method should be set to "after_state_change" of the state machine.
		"""
		if self.state != self._previous_state:
			super()._update_openhab_state()
			self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

			self._set_light_state()
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
		if self._item_sleeping_state is None:
			return False

		pre_sleep_prevent = False
		if self._config.pre_sleep_prevent:
			if callable(self._config.pre_sleep_prevent):
				pre_sleep_prevent = self._config.pre_sleep_prevent()
			if isinstance(self._config.pre_sleep_prevent, HABApp.openhab.items.OpenhabItem):
				pre_sleep_prevent = bool(self._config.pre_sleep_prevent)

		return bool(self._timeout_pre_sleep) and not pre_sleep_prevent

	def on_enter_auto_restoreState(self):  # pylint: disable=invalid-name
		"""On enter of state auto_restoreState."""
		self._restore_state = "auto_off" if self._restore_state == "auto_preoff" else self._restore_state

		if self._restore_state:
			self._set_state(self._restore_state)

	def _was_on_before(self) -> bool:
		"""Check whether the dimmer was on before

		:return: True if the dimmer was on before, else False
		"""
		return bool(self._brightness_before)

	def _set_timeouts(self) -> None:
		"""Set timeouts depending on the current day/night/sleep state."""
		if self._get_sleeping_activ():
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

	@abc.abstractmethod
	def _set_light_state(self) -> None:
		"""Set brightness to light."""

	# pylint: disable=too-many-branches, too-many-return-statements
	def _get_target_brightness(self) -> bool | float | None:
		"""Get configured brightness for the current day/night/sleep state

		:return: brightness value
		"""
		sleeping_active = self._get_sleeping_activ(True)

		if self.state == "auto_on":
			if self._previous_state == "manual":
				return None
			if self._previous_state in {"auto_preoff", "auto_leaving", "auto_presleep"}:
				return self._brightness_before

			# starting from here: previous state == auto_off
			if isinstance(self._state_observer.last_manual_event.value, (int, float)):
				return None
			if self._state_observer.last_manual_event.value == "INCREASE":
				return None

			if sleeping_active:
				brightness_from_config = self._config.on.sleeping.brightness
			elif bool(self._item_day):
				brightness_from_config = self._config.on.day.brightness
			else:
				brightness_from_config = self._config.on.night.brightness

			if brightness_from_config is True and self._state_observer.last_manual_event.value == "ON":
				return None

			return brightness_from_config

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
			if self._previous_state == "manual":
				return None
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

	def _get_sleeping_activ(self, include_pre_sleep: bool = False) -> bool:
		"""Get if sleeping is active.

		:param include_pre_sleep: if true, also pre sleep will be handled as sleeping
		:return: true if sleeping active
		"""
		sleep_states = [habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value] if include_pre_sleep else [habapp_rules.system.SleepState.SLEEPING.value]
		return getattr(self._item_sleeping_state, "value", "") in sleep_states

	def _cb_hand_on(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is triggered by the state observer if a manual ON command was detected.

		:param event: original trigger event
		"""
		self.hand_on()

	def _cb_hand_off(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is triggered by the state observer if a manual OFF command was detected.

		:param event: original trigger event
		"""
		self.hand_off()

	def _cb_manu(self, event: HABApp.openhab.events.ItemStateUpdatedEvent) -> None:
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
			self._restore_state = self._previous_state
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
			self._restore_state = self._previous_state
			self.sleep_started()
		elif event.value == habapp_rules.system.SleepState.AWAKE.value and self.state == "auto_presleep":
			self.sleep_aborted()


class LightSwitch(_LightBase):
	"""Rules class to manage basic light states.

		# KNX-things:
		Thing device T00_99_OpenHab_DimmerObserver "KNX OpenHAB dimmer observer"{
			Type switch             : light             "Light"             [ switch="1/1/10+1/1/13" ]
		}

		# Items:
		Switch    I01_01_Light              "Light [%s]"        {channel="knx:device:bridge:T00_99_OpenHab_DimmerObserver:light"}
		Switch    I00_00_Light_manual       "Light manual"

		# Rule init:
		habapp_rules.actors.light.LightSwitch(
			"I01_01_Light",
			manual_name="I00_00_Light_manual",
			presence_state_name="I999_00_Presence_state", # string item!
			sleeping_state_name="I999_00_Sleeping_state", # string item!
			day_name="I999_00_Day",
			config=CONFIG_TEST,
		)
		"""

	def __init__(self,
	             name_light: str,
	             manual_name: str,
	             presence_state_name: str,
	             day_name: str,
	             config: habapp_rules.actors.config.light.LightConfig,
	             sleeping_state_name: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None):
		"""Init of basic light object.

		:param name_light: name of OpenHAB light item (SwitchItem)
		:param manual_name: name of OpenHAB switch item to disable all automatic functions
		:param presence_state_name: name of OpenHAB presence state item
		:param day_name: name of OpenHAB switch item which is 'ON' during day and 'OFF' during night
		:param config: configuration of the light object
		:param sleeping_state_name: [optional] name of OpenHAB sleeping state item
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		:raises TypeError: if type of light_item is not supported
		"""
		light_item = HABApp.core.Items.get_item(name_light)
		if not isinstance(light_item, HABApp.openhab.items.switch_item.SwitchItem):
			raise TypeError(f"type: {type(light_item)} is not supported!")

		self._item_light = HABApp.openhab.items.SwitchItem.get_item(name_light)
		self._state_observer = habapp_rules.actors.state_observer.StateObserverSwitch(name_light, self._cb_hand_on, self._cb_hand_off)

		_LightBase.__init__(self, name_light, manual_name, presence_state_name, day_name, config, sleeping_state_name, name_state, state_label)

	def _update_openhab_state(self) -> None:
		_LightBase._update_openhab_state(self)

		if self.state == "auto_preoff":
			timeout = self.state_machine.get_state(self.state).timeout

			warn_thread_1 = threading.Thread(target=self.__trigger_warning, args=("auto_preoff", 0, 1), daemon=True)
			warn_thread_1.start()

			if timeout > 60:
				# add additional warning for long timeouts
				warn_thread_2 = threading.Thread(target=self.__trigger_warning, args=("auto_preoff", timeout / 2, 2), daemon=True)
				warn_thread_2.start()

	def __trigger_warning(self, state_name: str, wait_time: float, switch_off_amount: int) -> None:
		"""Trigger light switch off warning.

		:param state_name: name of state where the warning should be triggered. If different no command will be sent
		:param wait_time: time between start of the thread and switch off / on
		:param switch_off_amount: number of switch off
		"""

		if wait_time:
			time.sleep(wait_time)

		for idx in range(switch_off_amount):
			if self.state != state_name:
				break
			self._state_observer.send_command("OFF")
			time.sleep(0.2)
			if self.state != state_name:
				break
			self._state_observer.send_command("ON")
			if idx + 1 < switch_off_amount:
				time.sleep(0.5)

	def _set_light_state(self) -> None:
		"""Set brightness to light."""
		target_value = self._get_target_brightness()
		if target_value is None or self._previous_state is None:
			# don't change value if target_value is None or _set_light_state will be called during init (_previous_state == None)
			return

		target_value = "ON" if target_value else "OFF"
		self._instance_logger.debug(f"set brightness {target_value}")
		self._state_observer.send_command(target_value)


class LightDimmer(_LightBase):
	"""Rules class to manage basic light states.

	# KNX-things:
	Thing device T00_99_OpenHab_DimmerObserver "KNX OpenHAB dimmer observer"{
		Type dimmer             : light             "Light"             [ switch="1/1/10", position="1/1/13+<1/1/15" ]
		Type dimmer-control     : light_ctr         "Light control"     [ increaseDecrease="1/1/12"]
		Type dimmer             : light_group       "Light Group"       [ switch="1/1/240", position="1/1/243"]
	}

	# Items:
	Dimmer    I01_01_Light              "Light [%s]"        {channel="knx:device:bridge:T00_99_OpenHab_DimmerObserver:light"}
	Dimmer    I01_01_Light_ctr          "Light ctr"         {channel="knx:device:bridge:T00_99_OpenHab_DimmerObserver:light_ctr"}
	Dimmer    I01_01_Light_group        "Light Group"       {channel="knx:device:bridge:T00_99_OpenHab_DimmerObserver:light_group"}
	Switch    I00_00_Light_manual       "Light manual"

	# Rule init:
	habapp_rules.actors.light.LightDimmer(
		"I01_01_Light",
		control_names=["I01_01_Light_ctr"],
		manual_name="I00_00_Light_manual",
		presence_state_name="I999_00_Presence_state", # string item!
		sleeping_state_name="I999_00_Sleeping_state", # string item!
		day_name="I999_00_Day",
		config=CONFIG_TEST,
		group_names=["I01_01_Light_group"]
	)
	"""

	trans = copy.deepcopy(_LightBase.trans)
	trans.append({"trigger": "hand_changed", "source": "auto_on", "dest": "auto_on"})

	# pylint: disable=too-many-arguments
	def __init__(self,
	             name_light: str,
	             control_names: list[str],
	             manual_name: str,
	             presence_state_name: str,
	             day_name: str,
	             config: habapp_rules.actors.config.light.LightConfig,
	             sleeping_state_name: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None,
	             group_names: list[str] | None = None) -> None:
		"""Init of basic light object.

		:param name_light: name of OpenHAB light item (DimmerItem)
		:param control_names: names of OpenHab items which must be configured as control (-ctr) items. This can be used for KNX items to detect increase / decrease commands from physical wall controllers
		:param manual_name: name of OpenHAB switch item to disable all automatic functions
		:param presence_state_name: name of OpenHAB presence state item
		:param day_name: name of OpenHAB switch item which is 'ON' during day and 'OFF' during night
		:param config: configuration of the light object
		:param sleeping_state_name: [optional] name of OpenHAB sleeping state item
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		:param group_names: list of group items where the light is a part of. Group item type must match with type of the light item
		:raises TypeError: if type of light_item is not supported
		"""
		light_item = HABApp.core.Items.get_item(name_light)
		if not isinstance(light_item, HABApp.openhab.items.dimmer_item.DimmerItem):
			raise TypeError(f"type: {type(light_item)} is not supported!")

		self._item_light = HABApp.openhab.items.DimmerItem.get_item(name_light)
		self._state_observer = habapp_rules.actors.state_observer.StateObserverDimmer(name_light, self._cb_hand_on, self._cb_hand_off, self._cb_hand_changed, control_names=control_names, group_names=group_names)

		_LightBase.__init__(self, name_light, manual_name, presence_state_name, day_name, config, sleeping_state_name,name_state, state_label)

	def _set_light_state(self) -> None:
		"""Set brightness to light."""
		target_value = self._get_target_brightness()
		if target_value is None or self._previous_state is None:
			# don't change value if target_value is None or _set_light_state will be called during init (_previous_state == None)
			return

		if isinstance(target_value, bool):
			if target_value:
				target_value = "ON"
			else:
				target_value = "OFF"
		self._instance_logger.debug(f"set brightness {target_value}")
		self._state_observer.send_command(target_value)

	def _cb_hand_changed(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent | HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered by the state observer if a manual OFF command was detected.

		:param event: original trigger event
		"""
		if isinstance(event, HABApp.openhab.events.ItemStateChangedEvent) and abs(event.value - event.old_value) > 5:
			self.hand_changed()


# pylint: disable=protected-access
class _LightExtendedMixin:
	"""Mixin class for adding door and motion functionality"""
	states: dict
	trans: list
	state: str
	state_machine: habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout
	_config: habapp_rules.actors.config.light.LightConfigExtended
	_get_sleeping_activ: typing.Callable[[bool | None], bool]
	_item_day: HABApp.openhab.items.SwitchItem

	def __init__(self, config: habapp_rules.actors.config.light.LightConfigExtended, name_motion: str | None = None, door_names: list[str] | None = None):
		"""Init mixin class.

		:param config: config of light object
		:param name_motion: [optional] name of OpenHAB motion item (SwitchItem)
		:param door_names: [optional] list of OpenHAB door items (ContactItem)
		"""
		self.states = _LightExtendedMixin._add_additional_states(self.states)
		self.trans = _LightExtendedMixin._add_additional_transitions(self.trans)

		door_names = door_names if door_names else []

		self._timeout_motion = 0
		self._timeout_door = 0

		self._item_motion = HABApp.openhab.items.switch_item.SwitchItem.get_item(name_motion) if name_motion else None
		self._items_door = [HABApp.openhab.items.contact_item.ContactItem.get_item(name) for name in door_names]

		self._hand_off_lock_time = config.hand_off_lock_time
		self._hand_off_timestamp = 0

	@staticmethod
	def _add_additional_states(states_dict: dict) -> dict:
		"""Add additional states for door and motion.

		:param states_dict: current state dictionary
		:return: current + new states
		"""
		states_dict = copy.deepcopy(states_dict)
		states_dict[1]["children"].append({"name": "door", "timeout": 999, "on_timeout": "door_timeout"})
		states_dict[1]["children"].append({"name": "motion", "timeout": 999, "on_timeout": "motion_timeout"})
		return states_dict

	@staticmethod
	def _add_additional_transitions(transitions_list: list[dict]) -> list[dict]:
		"""Add additional transitions for door and motion

		:param transitions_list: current transitions
		:return: current + new transitions
		"""
		transitions_list = copy.deepcopy(transitions_list)

		transitions_list.append({"trigger": "motion_on", "source": "auto_door", "dest": "auto_motion", "conditions": "_motion_configured"})
		transitions_list.append({"trigger": "motion_on", "source": "auto_off", "dest": "auto_motion", "conditions": ["_motion_configured", "_motion_door_allowed"]})
		transitions_list.append({"trigger": "motion_on", "source": "auto_preoff", "dest": "auto_motion", "conditions": "_motion_configured"})
		transitions_list.append({"trigger": "motion_off", "source": "auto_motion", "dest": "auto_preoff", "conditions": "_pre_off_configured"})
		transitions_list.append({"trigger": "motion_off", "source": "auto_motion", "dest": "auto_off", "unless": "_pre_off_configured"})
		transitions_list.append({"trigger": "motion_timeout", "source": "auto_motion", "dest": "auto_preoff", "conditions": "_pre_off_configured", "before": "_log_motion_timeout_warning"})
		transitions_list.append({"trigger": "motion_timeout", "source": "auto_motion", "dest": "auto_off", "unless": "_pre_off_configured", "before": "_log_motion_timeout_warning"})
		transitions_list.append({"trigger": "hand_off", "source": "auto_motion", "dest": "auto_off"})

		transitions_list.append({"trigger": "door_opened", "source": "auto_off", "dest": "auto_door", "conditions": ["_door_configured", "_motion_door_allowed"]})
		transitions_list.append({"trigger": "door_timeout", "source": "auto_door", "dest": "auto_preoff", "conditions": "_pre_off_configured"})
		transitions_list.append({"trigger": "door_timeout", "source": "auto_door", "dest": "auto_off", "unless": "_pre_off_configured"})
		transitions_list.append({"trigger": "door_closed", "source": "auto_leaving", "dest": "auto_off", "conditions": "_door_off_leaving_configured"})
		transitions_list.append({"trigger": "hand_off", "source": "auto_door", "dest": "auto_off"})

		transitions_list.append({"trigger": "leaving_started", "source": ["auto_motion", "auto_door"], "dest": "auto_leaving", "conditions": "_leaving_configured"})
		transitions_list.append({"trigger": "sleep_started", "source": ["auto_motion", "auto_door"], "dest": "auto_presleep", "conditions": "_pre_sleep_configured"})

		return transitions_list

	def add_additional_callbacks(self) -> None:
		"""Add additional callbacks for motion and door items."""
		if self._item_motion is not None:
			self._item_motion.listen_event(self._cb_motion, HABApp.openhab.events.ItemStateChangedEventFilter())
		for item_door in self._items_door:
			item_door.listen_event(self._cb_door, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _get_initial_state(self, default_value: str = "") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		initial_state = _LightBase._get_initial_state(self, default_value)

		if initial_state == "auto_on" and bool(self._item_motion) and self._motion_configured():
			initial_state = "auto_motion"
		return initial_state

	def _set_timeouts(self) -> None:
		"""Set timeouts depending on the current day/night/sleep state."""
		_LightBase._set_timeouts(self)

		# set timeouts of additional states
		if self._get_sleeping_activ():
			self._timeout_motion = getattr(self._config.motion.sleeping if self._config.motion else None, "timeout", None)
			self._timeout_door = getattr(self._config.door.sleeping if self._config.door else None, "timeout", None)

		elif bool(self._item_day):
			self._timeout_motion = getattr(self._config.motion.day if self._config.motion else None, "timeout", None)
			self._timeout_door = getattr(self._config.door.day if self._config.door else None, "timeout", None)
		else:
			self._timeout_motion = getattr(self._config.motion.night if self._config.motion else None, "timeout", None)
			self._timeout_door = getattr(self._config.door.night if self._config.door else None, "timeout", None)

		self.state_machine.states["auto"].states["motion"].timeout = self._timeout_motion
		self.state_machine.states["auto"].states["door"].timeout = self._timeout_door

	def _get_target_brightness(self) -> bool | float | None:
		"""Get configured brightness for the current day/night/sleep state. Must be called before _get_target_brightness of base class

		:return: brightness value
		:raises habapp_rules.core.exceptions.HabAppRulesException: if current state is not supported
		"""
		if self.state == "auto_motion":
			if self._get_sleeping_activ(True):
				return getattr(self._config.motion.sleeping if self._config.motion else None, "brightness", None)
			if bool(self._item_day):
				return getattr(self._config.motion.day if self._config.motion else None, "brightness", None)
			return getattr(self._config.motion.night if self._config.motion else None, "brightness", None)

		if self.state == "auto_door":
			if self._get_sleeping_activ(True):
				return getattr(self._config.door.sleeping if self._config.door else None, "brightness", None)
			if bool(self._item_day):
				return getattr(self._config.door.day if self._config.door else None, "brightness", None)
			return getattr(self._config.door.night if self._config.door else None, "brightness", None)

		return _LightBase._get_target_brightness(self)

	def _door_configured(self) -> bool:
		"""Check whether door functionality is configured for the current day/night state

		:return: True if door functionality is configured
		"""
		if not self._items_door:
			return False
		return bool(self._timeout_door)

	def _door_off_leaving_configured(self) -> bool:
		"""Check whether door-off functionality is configured for the current day/night state

		:return: True if door-off is configured
		"""
		return self._config.off_at_door_closed_during_leaving

	def _motion_configured(self) -> bool:
		"""Check whether motion functionality is configured for the current day/night state

		:return: True if motion functionality is configured
		"""
		if self._item_motion is None:
			return False
		return bool(self._timeout_motion)

	def _motion_door_allowed(self) -> bool:
		"""Check if transition to motion and door state is allowed

		:return: True if transition is allowed
		"""
		return time.time() - self._hand_off_timestamp > self._hand_off_lock_time

	def _cb_hand_off(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is triggered by the state observer if a manual OFF command was detected.

		:param event: original trigger event
		"""
		self._hand_off_timestamp = time.time()
		_LightBase._cb_hand_off(self, event)

	def _cb_motion(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the motion state changed.

		:param event: trigger event
		"""
		if event.value == "ON":
			self.motion_on()
		else:
			self.motion_off()

	def _cb_door(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if a door state changed.

		:param event: trigger event
		"""
		if event.value == "OPEN":
			# every open of a single door calls door_opened()
			self.door_opened()

		if event.value == "CLOSED" and all(door.is_closed() for door in self._items_door):
			# only if all doors are closed door_closed() is called
			self.door_closed()

	def _log_motion_timeout_warning(self):
		"""Log warning if motion state was left because of timeout."""
		self._instance_logger.warning("Timeout of motion was triggered, before motion stopped. Thing about to increase motion timeout!")


# pylint: disable=protected-access
class LightSwitchExtended(_LightExtendedMixin, LightSwitch):
	"""Extended Light.

	Example config is given at Light base class.
	With this class additionally motion or door items can be given.
	"""

	# pylint: disable=too-many-arguments
	def __init__(self, name_light: str,
	             manual_name: str,
	             presence_state_name: str,
	             day_name: str,
	             config: habapp_rules.actors.config.light.LightConfigExtended, sleeping_state_name: str | None = None,
	             name_motion: str | None = None,
	             door_names: list[str] | None = None,
	            name_state: str | None = None,
	             state_label: str | None = None):
		"""Init of extended light object.

		:param name_light: name of OpenHAB light item (SwitchItem)
		:param manual_name: name of OpenHAB switch item to disable all automatic functions
		:param presence_state_name: name of OpenHAB presence state item
		:param day_name: name of OpenHAB switch item which is 'ON' during day and 'OFF' during night
		:param config: configuration of the light object
		:param sleeping_state_name: [optional] name of OpenHAB sleeping state item
		:param name_motion: [optional] name of OpenHAB motion item (SwitchItem)
		:param door_names: [optional] list of OpenHAB door items (ContactItem)
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		:raises TypeError: if type of light_item is not supported
		"""
		_LightExtendedMixin.__init__(self, config, name_motion, door_names)
		LightSwitch.__init__(self, name_light, manual_name, presence_state_name, day_name, config, sleeping_state_name,name_state, state_label)

		_LightExtendedMixin.add_additional_callbacks(self)


# pylint: disable=protected-access
class LightDimmerExtended(_LightExtendedMixin, LightDimmer):
	"""Extended Light.

	Example config is given at Light base class.
	With this class additionally motion or door items can be given.
	"""

	# pylint:disable=too-many-arguments
	def __init__(self, name_light: str,
	             control_names: list[str],
	             manual_name: str,
	             presence_state_name: str,
	             day_name: str,
	             config: habapp_rules.actors.config.light.LightConfigExtended,
	             sleeping_state_name: str | None = None,
	             name_motion: str | None = None,
	             door_names: list[str] | None = None,
	            name_state: str | None = None,
	             state_label: str | None = None,
	             group_names: list[str] | None = None) -> None:
		"""Init of extended light object.

		:param name_light: name of OpenHAB light item (DimmerItem)
		:param control_names: names of OpenHab items which must be configured as control (-ctr) items. This can be used for KNX items to detect increase / decrease commands from physical wall controllers
		:param manual_name: name of OpenHAB switch item to disable all automatic functions
		:param presence_state_name: name of OpenHAB presence state item
		:param day_name: name of OpenHAB switch item which is 'ON' during day and 'OFF' during night
		:param config: configuration of the light object
		:param sleeping_state_name: [optional] name of OpenHAB sleeping state item
		:param name_motion: [optional] name of OpenHAB motion item (SwitchItem)
		:param door_names: [optional] list of OpenHAB door items (ContactItem)
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		:param group_names: list of group items where the light is a part of. Group item type must match with type of the light item
		:raises TypeError: if type of light_item is not supported
		"""
		_LightExtendedMixin.__init__(self, config, name_motion, door_names)
		LightDimmer.__init__(self, name_light, control_names, manual_name, presence_state_name, day_name, config, sleeping_state_name, name_state, state_label, group_names)

		_LightExtendedMixin.add_additional_callbacks(self)
