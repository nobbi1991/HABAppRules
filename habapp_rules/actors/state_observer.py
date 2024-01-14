"""Implementations for observing states of switch / dimmer / roller shutter."""
from __future__ import annotations

import abc
import logging
import threading
import time
import typing

import HABApp
import HABApp.openhab.items

import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.timeout_list

LOGGER = logging.getLogger(__name__)

EventTypes = typing.Union[HABApp.openhab.events.ItemStateChangedEvent, HABApp.openhab.events.ItemCommandEvent]
CallbackType = typing.Callable[[EventTypes], None]


class _StateObserverBase(HABApp.Rule, abc.ABC):
	"""Base class for observer classes."""

	def __init__(self, item_name: str, control_names: list[str] | None = None, group_names: list[str] | None = None, value_tolerance: int = 0):
		"""Init state observer for switch item.

		:param item_name: Name of observed item
		:param control_names: list of control items.
		:param group_names: list of group items where the item is a part of. Group item type must match with type of item_name
		:param value_tolerance: used by all observers which handle numbers. It can be used to allow a difference when comparing new and old values.
		"""
		self._value_tolerance = value_tolerance

		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, item_name)

		self._last_manual_event = HABApp.openhab.events.ItemCommandEvent("", None)

		self._item = HABApp.openhab.items.OpenhabItem.get_item(item_name)

		self.__control_items = [HABApp.openhab.items.OpenhabItem.get_item(name) for name in control_names] if control_names else []
		self.__group_items = [HABApp.openhab.items.OpenhabItem.get_item(name) for name in group_names] if group_names else []
		self.__check_item_types()

		self._value = self._item.value
		self._group_last_event = 0

		self._item.listen_event(self._cb_item, HABApp.openhab.events.ItemStateChangedEventFilter())
		for control_item in self.__control_items:
			control_item.listen_event(self._cb_control_item, HABApp.openhab.events.ItemCommandEventFilter())
		for group_item in self.__group_items:
			group_item.listen_event(self._cb_group_item, HABApp.openhab.events.ItemStateUpdatedEventFilter())

	@property
	def value(self) -> float | bool:
		"""Get the current state / value of the observed item."""
		return self._value

	@property
	def last_manual_event(self) -> EventTypes:
		"""Get the last manual event."""
		return self._last_manual_event

	def __check_item_types(self) -> None:
		"""Check if all command and control items have the correct type.

		:raises TypeError: if one item has the wrong type"""
		target_type = type(self._item)

		wrong_types = []
		for item in self.__control_items + self.__group_items:
			if not isinstance(item, target_type):
				wrong_types.append(f"{item.name} <{type(item).__name__}>")

		if wrong_types:
			self._instance_logger.error(msg := f"Found items with wrong item type. Expected: {target_type.__name__}. Wrong: {' | '.join(wrong_types)}")
			raise TypeError(msg)

	@abc.abstractmethod
	def send_command(self, value: float | str) -> None:
		"""Send brightness command to light (this should be used by rules, to not trigger a manual action)

		:param value: Value to send to the light
		:raises ValueError: if value has wrong format
		"""

	def _cb_item(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		"""
		self._check_manual(event)

	def _cb_group_item(self, event: HABApp.openhab.events.ItemStateUpdatedEvent):
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		"""
		if event.value in {"ON", "OFF"} and time.time() - self._group_last_event > 0.3:  # this is some kind of workaround. For some reason all events are doubled.
			self._group_last_event = time.time()
			self._check_manual(event)

	@abc.abstractmethod
	def _cb_control_item(self, event: HABApp.openhab.events.ItemCommandEvent):
		"""Callback, which is called if a command event of one of the control items was detected.

		:param event: event, which triggered this callback
		"""

	@abc.abstractmethod
	def _check_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:raises ValueError: if event is not supported
		"""

	def _trigger_callback(self, cb_name: str, event: EventTypes) -> None:
		"""Trigger a manual detected callback.

		:param cb_name: name of callback method
		:param event: event which triggered the callback
		"""
		self._last_manual_event = event
		callback: CallbackType = getattr(self, cb_name)
		callback(event)

	def _compare_values_with_tolerance(self, value_1: float, value_2: float) -> bool:
		"""Compare values with tolerance

		:param value_1: first value
		:param value_2: second value
		:return: true if values are the same (including the offset), false if not
		"""
		return abs((value_1 or 0) - (value_2 or 0)) > self._value_tolerance


class StateObserverSwitch(_StateObserverBase):
	"""Class to observe the on/off state of a switch item.

	This class is normally not used standalone. Anyway here is an example config:

	# KNX-things:
	Thing device T00_99_OpenHab_DimmerSwitch "KNX OpenHAB switch observer"{
        Type switch             : switch             "Switch"             [ switch="1/1/10" ]
    }

    # Items:
	    Switch    I01_01_Switch    "Switch [%s]" {channel="knx:device:bridge:T00_99_OpenHab_DimmerSwitch:switch"}

	# Rule init:
	habapp_rules.actors.state_observer.StateObserverSwitch("I01_01_Switch", callback_on, callback_off)
	"""

	def __init__(self, item_name: str, cb_on: CallbackType, cb_off: CallbackType):
		"""Init state observer for switch item.

		:param item_name: Name of switch item
		:param cb_on: callback which should be called if manual_on was detected
		:param cb_off: callback which should be called if manual_off was detected
		"""
		self._cb_on = cb_on
		self._cb_off = cb_off
		_StateObserverBase.__init__(self, item_name)
		self._value = self._value == "ON"

	def _check_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:raises ValueError: if event is not supported
		"""
		if event.value == "ON" and not self._value:
			self._value = True
			self._trigger_callback("_cb_on", event)

		elif event.value == "OFF" and self._value:
			self._value = False
			self._trigger_callback("_cb_off", event)

	def _cb_control_item(self, event: HABApp.openhab.events.ItemCommandEvent):  # not used by StateObserverSwitch
		"""Callback, which is called if a command event of one of the control items was detected.

		:param event: event, which triggered this callback
		"""

	def send_command(self, value: str) -> None:
		"""Send brightness command to light (this should be used by rules, to not trigger a manual action)

		:param value: Value to send to the light
		:raises ValueError: if value has wrong format
		"""
		if value == "ON":
			self._value = True

		elif value == "OFF":
			self._value = False
		else:
			raise ValueError(f"The given value is not supported for StateObserverSwitch: {value}")

		self._item.oh_send_command(value)


class StateObserverDimmer(_StateObserverBase):
	"""Class to observe the on / off / change events of a dimmer item.

	Known limitation: if the items of group_names are KNX-items, the channel types must be dimmer (not dimmer-control)
	This class is normally not used standalone. Anyway here is an example config:

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

	# Rule init:
	habapp_rules.actors.state_observer.StateObserverDimmer(
			"I01_01_Light",
			control_names=["I01_01_Light_ctr"],
			group_names=["I01_01_Light_group"],
			cb_on=callback_on,
			cb_off=callback_off,
			cb_brightness_change=callback_change)
	"""

	def __init__(self, item_name: str, cb_on: CallbackType, cb_off: CallbackType, cb_brightness_change: CallbackType | None = None, control_names: list[str] | None = None, group_names: list[str] | None = None, value_tolerance: int = 0) -> None:
		"""Init state observer for dimmer item.

		:param item_name: Name of dimmer item
		:param cb_on: callback which is called if manual_on was detected
		:param cb_off: callback which is called if manual_off was detected
		:param cb_brightness_change: callback which is called if dimmer is on and brightness changed
		:param control_names: list of control items. They are used to also respond to switch on/off via INCREASE/DECREASE
		:param group_names: list of group items where the item is a part of. Group item type must match with type of item_name
		:param value_tolerance: the tolerance can be used to allow a difference when comparing new and old values.
		"""

		_StateObserverBase.__init__(self, item_name, control_names, group_names, value_tolerance)

		self._cb_on = cb_on
		self._cb_off = cb_off
		self._cb_brightness_change = cb_brightness_change

	def _check_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		"""
		if isinstance(event.value, (int, float)):
			if event.value > 0 and self._value == 0:
				self._value = event.value
				self._trigger_callback("_cb_on", event)

			elif event.value == 0 and self._value > 0:
				self._value = 0
				self._trigger_callback("_cb_off", event)

			elif self._compare_values_with_tolerance(event.value, self._value):
				self._value = event.value
				self._trigger_callback("_cb_brightness_change", event)

		elif event.value == "ON" and self._value == 0:
			self._value = 100
			self._trigger_callback("_cb_on", event)

		elif event.value == "OFF" and self._value > 0:
			self._value = 0
			self._trigger_callback("_cb_off", event)

	def _cb_control_item(self, event: HABApp.openhab.events.ItemCommandEvent):
		"""Callback, which is called if a command event of one of the control items was detected.

		:param event: event, which triggered this callback
		"""
		if event.value == "INCREASE" and self._value == 0:
			self._value = 100
			self._trigger_callback("_cb_on", event)

	def send_command(self, value: float | str) -> None:
		"""Send brightness command to light (this should be used by rules, to not trigger a manual action)

		:param value: Value to send to the light
		:raises ValueError: if value has wrong format
		"""
		if isinstance(value, (int, float)):
			self._value = value

		elif value == "ON":
			self._value = 100

		elif value == "OFF":
			self._value = 0

		else:
			raise ValueError(f"The given value is not supported for StateObserverDimmer: {value}")

		self._item.oh_send_command(value)


class StateObserverRollerShutter(_StateObserverBase):
	"""Class to observe manual controls of a roller shutter item.

		This class is normally not used standalone. Anyway, here is an example config:

		# KNX-things:
		Thing device T00_99_OpenHab_RollershutterObserver "KNX OpenHAB rollershutter observer"{
	        Type rollershutter             : shading             "Shading"             [ upDown="1/1/10", position="1/1/13+<1/1/15" ]
	        Type rollershutter-control     : shading_ctr         "Shading control"     [ upDown="1/1/10", position="1/1/13+<1/1/15" ]
	        Type rollershutter             : shading_group       "Shading Group"       [ upDown="1/1/110", position="1/1/113+<1/1/115" ]
	    }

	    # Items:
	    Rollershutter    I_Rollershutter              "Rollershutter [%s]"        {channel="knx:device:bridge:T00_99_OpenHab_RollershutterObserver:Rollershutter"}
		Rollershutter    I_Rollershutter_ctr          "Rollershutter ctr"         {channel="knx:device:bridge:T00_99_OpenHab_RollershutterObserver:Rollershutter_ctr"}
		Rollershutter    I_Rollershutter_group        "Rollershutter Group"       {channel="knx:device:bridge:T00_99_OpenHab_RollershutterObserver:Rollershutter_group"}

		# Rule init:
		habapp_rules.actors.state_observer.StateObserverRollerShutter(
				"I_Rollershutter",
				control_names=["I_Rollershutter_ctr"],
				group_names=["I_Rollershutter_group"],
				cb_manual=callback_on
				)
		"""

	def __init__(self, item_name: str, cb_manual: CallbackType, control_names: list[str] | None = None, group_names: list[str] | None = None, value_tolerance: int = 0) -> None:
		"""Init state observer for dimmer item.

		:param item_name: Name of dimmer item
		:param cb_manual: callback which is called if a manual interaction was detected
		:param control_names: list of control items. They are used to also respond to switch on/off via INCREASE/DECREASE
		:param group_names: list of group items where the item is a part of. Group item type must match with type of item_name
		:param value_tolerance: the tolerance can be used to allow a difference when comparing new and old values.
		"""
		self._value_tolerance = value_tolerance
		_StateObserverBase.__init__(self, item_name, control_names, group_names, value_tolerance)

		self._cb_manual = cb_manual

	def _check_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		if isinstance(event.value, (int, float)) and self._compare_values_with_tolerance(event.value, self._value):
			self._value = event.value
			self._trigger_callback("_cb_manual", event)

	def _cb_control_item(self, event: HABApp.openhab.events.ItemCommandEvent):
		if event.value == "DOWN":
			self._value = 100
			self._trigger_callback("_cb_manual", event)

		elif event.value == "UP":
			self._value = 0
			self._trigger_callback("_cb_manual", event)

	def send_command(self, value: float) -> None:
		if not isinstance(value, (int, float)):
			raise ValueError(f"The given value is not supported for StateObserverDimmer: {value}")

		self._value = value
		self._item.oh_send_command(value)


class StateObserverNumber(_StateObserverBase):
	"""Class to observe the state of a number item.

	This class is normally not used standalone. Anyway here is an example config:

	# KNX-things:
	Thing device T00_99_OpenHab_DimmerNumber "KNX OpenHAB number observer"{
        Type number             : number             "Switch"             [ ga="1/1/10" ]
    }

    # Items:
	    Number    I01_01_Number    "Switch [%s]" {channel="knx:device:bridge:T00_99_OpenHab_DimmerNumber:number"}

	# Rule init:
	habapp_rules.actors.state_observer.StateObserverNumber("I01_01_Number", callback_value_changed)
	"""

	def __init__(self, item_name: str, cb_manual: CallbackType, value_tolerance: int = 0) -> None:
		"""Init state observer for switch item.

		:param item_name: Name of switch item
		:param cb_manual: callback which should be called if manual change was detected
		:param value_tolerance: the tolerance can be used to allow a difference when comparing new and old values.
		"""
		self._cb_manual = cb_manual
		_StateObserverBase.__init__(self, item_name, value_tolerance=value_tolerance)

	def _check_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:raises ValueError: if event is not supported
		"""
		if self._value is None:
			self._value = event.value
			return

		if self._compare_values_with_tolerance(event.value, self._value):
			self._value = event.value
			self._trigger_callback("_cb_manual", event)

	def _cb_control_item(self, event: HABApp.openhab.events.ItemCommandEvent):  # not used by StateObserverNumber
		"""Callback, which is called if a command event of one of the control items was detected.

		:param event: event, which triggered this callback
		"""

	def send_command(self, value: int | float) -> None:
		"""Send brightness command to light (this should be used by rules, to not trigger a manual action)

		:param value: Value to send to the light
		:raises ValueError: if value has wrong format
		"""
		if not isinstance(value, (int, float)):
			raise ValueError(f"The given value is not supported for StateObserverNumber: {value}")
		self._value = value
		self._item.oh_send_command(value)


class StateObserverSlat(StateObserverNumber):

	def __init__(self, item_name: str, cb_manual: CallbackType, value_tolerance: int = 0) -> None:
		"""Init state observer for switch item.

		:param item_name: Name of switch item
		:param cb_manual: callback which should be called if manual change was detected
		:param value_tolerance: the tolerance can be used to allow a difference when comparing new and old values.
		"""
		self.__timer_manual: threading.Timer | None = None
		StateObserverNumber.__init__(self, item_name, cb_manual, value_tolerance)

	def _check_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		if event.value in (0, 100):
			self.__timer_manual = threading.Timer(3, self.__cb_check_manual_delayed, [event])
		else:
			if self.__timer_manual:
				self.__timer_manual.cancel()
				self.__timer_manual = None
			StateObserverNumber._check_manual(self, event)

	def __cb_check_manual_delayed(self, event):
		StateObserverNumber._check_manual(self, event)

	def on_rule_removed(self):
		if self.__timer_manual:
			self.__timer_manual.cancel()
			self.__timer_manual = None
