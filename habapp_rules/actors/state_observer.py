"""Implementations for observing states of switch / dimmer / roller shutter."""
from __future__ import annotations

import abc
import logging
import typing

import HABApp
import HABApp.openhab.interface
import HABApp.openhab.items

import habapp_rules.core.logger
import habapp_rules.core.timeout_list

LOGGER = logging.getLogger(__name__)

EventTypes = typing.Union[HABApp.openhab.events.ItemStateChangedEvent, HABApp.openhab.events.ItemCommandEvent]
CallbackType = typing.Callable[[EventTypes, str], None]


class StateObserverBase(HABApp.Rule, abc.ABC):
	"""Base class for observer classes."""

	def __init__(self, item_name: str, control_names: list[str]):
		"""Init state observer for switch item.

		:param item_name: Name of observed item
		:param control_names: list of control items
		"""
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, item_name)

		self._expected_values = habapp_rules.core.timeout_list.TimeoutList()
		self._last_manual_event = HABApp.openhab.events.ItemCommandEvent()

		self._item = HABApp.openhab.items.OpenhabItem.get_item(item_name)

		self.__control_items = [HABApp.openhab.items.OpenhabItem.get_item(name) for name in control_names] if control_names else []
		self.__check_item_types()

		self._value = self._item.value

		self._item.listen_event(self._cb_state_change, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item.listen_event(self._cb_command, HABApp.openhab.events.ItemCommandEventFilter())
		HABApp.util.EventListenerGroup().add_listener(self.__control_items, self.__cb_control, HABApp.openhab.events.ItemCommandEventFilter()).listen()

	@property
	def value(self) -> float:
		"""Get the current brightness value of the light."""
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
		for item in self.__control_items:
			if not isinstance(item, target_type):
				wrong_types.append(f"{item.name} <{type(item).__name__}>")

		if wrong_types:
			self._instance_logger.error(msg := f"Found items with wrong item type. Expected: {target_type.__name__}. Wrong: {' | '.join(wrong_types)}")
			raise TypeError(msg)

	def send_command(self, value: float | str) -> None:
		"""Send brightness command to light (this should be used by rules, to not trigger a manual action)

		:param value: Value to send to the light
		:raises ValueError: if value has wrong format
		"""
		self._expected_values.append(value, 20)
		self._item.oh_send_command(value)

	def _cb_command(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is called if a command event of one of the command items was detected.

		:param event: event, which triggered this callback
		"""
		if event.value in self._expected_values:
			return

		self._check_manual(event, "Manual from OpenHAB")
		self._expected_values.append(event.value, 20)

	def _cb_state_change(self, event: HABApp.openhab.events.ItemStateChangedEvent, call_check_manual: bool = True):
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		:param call_check_manual: If true: _check_manual() will be called, otherwise not. This is for dimmer lights
		"""
		if call_check_manual:
			self._check_manual(event, "Manual from extern")
		self._value = event.value

	def __cb_control(self, event: HABApp.openhab.events.ItemCommandEvent):
		"""Callback, which is called if a command event of one of the control items was detected.

		:param event: event, which triggered this callback
		"""
		print(event)
		self._check_manual(event, "Manual from extern")

	@abc.abstractmethod
	def _check_manual(self, event: HABApp.openhab.events.base_event.OpenhabEvent, message: str) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		:raises ValueError: if event is not supported
		"""

	def _trigger_callback(self, cb_name: str, event: EventTypes, message: str) -> None:
		"""Trigger a manual detected callback.

		:param cb_name: name of callback method
		:param event: event which triggered the callback
		:param message: message of the callback
		"""
		self._last_manual_event = event
		callback: CallbackType = getattr(self, cb_name)
		callback(event, message)


class StateObserverSwitch(StateObserverBase):
	"""Class to observe the on/off state of a switch item."""

	def __init__(self, item_name: str, cb_on: CallbackType, cb_off: CallbackType, control_names: list[str] = None):
		"""Init state observer for switch item.

		:param item_name: Name of switch item
		:param cb_on: callback which should be called if manual_on was detected
		:param cb_off: callback which should be called if manual_off was detected
		:param control_names: list of control items
		"""
		self._cb_on = cb_on
		self._cb_off = cb_off
		StateObserverBase.__init__(self, item_name, control_names)

	def _check_manual(self, event: EventTypes, message: str) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		:raises ValueError: if event is not supported
		"""
		if event.value != self.value:
			if event.value == "ON":
				self._trigger_callback("_cb_on", event, message)
			elif event.value == "OFF":
				self._trigger_callback("_cb_off", event, message)
			else:
				raise ValueError(f"Event '{event.value}' is not supported!")

	def _cb_state_change(self, event: HABApp.openhab.events.ItemStateChangedEvent, call_check_manual: bool = True):
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		:param call_check_manual: If true: _check_manual() will be called, otherwise not. This is for dimmer lights
		"""
		if event.value in self._expected_values:
			self._expected_values.remove(event.value)
			call_check_manual = False

		super()._cb_state_change(event, call_check_manual)


class StateObserverDimmer(StateObserverBase):
	"""Class to observe the on/off state of a dimmer item."""

	def __init__(self, item_name: str, cb_on: CallbackType, cb_off: CallbackType, cb_brightness_change: CallbackType | None = None, control_names: list[str] = None) -> None:
		"""Init state observer for dimmer item.

		:param item_name: Name of dimmer item
		:param cb_on: callback which is called if manual_on was detected
		:param cb_off: callback which is called if manual_off was detected
		:param cb_brightness_change: callback which is called if dimmer is on and brightness changed
		:param control_names: list of control items
		"""
		self._cb_on = cb_on
		self._cb_off = cb_off
		self._cb_brightness_change = cb_brightness_change

		StateObserverBase.__init__(self, item_name, control_names)

	def _cb_state_change(self, event: HABApp.openhab.events.ItemStateChangedEvent, call_check_manual: bool = True) -> None:
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		:param call_check_manual: If true: _check_manual() will be called, otherwise not. This is used to avoid calling manual check if this class is waiting for a state update
		"""
		if event.value is None:
			self._instance_logger.warning("Received None command. Check your OpenHAB configuration if you have set increaseDecrease for the KNX channel")
			return

		if event.value in self._expected_values:
			self._expected_values.remove(event.value)
			call_check_manual = False
		elif isinstance(event.value, (float, int)):
			if event.value > 0 and "ON" in self._expected_values:
				self._expected_values.remove("ON")
				call_check_manual = False
			elif event.value == 0 and "OFF" in self._expected_values:
				self._expected_values.remove("OFF")
				call_check_manual = False

		super()._cb_state_change(event, call_check_manual)

	def _check_manual(self, event: EventTypes, message: str) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		:raises ValueError: if event is not supported
		"""
		if event.value == "ON" and self.value == 0:
			self._trigger_callback("_cb_on", event, message)
		elif event.value == "OFF" and self.value > 0:
			self._trigger_callback("_cb_off", event, message)
		elif isinstance(event.value, (int, float)):
			if event.value > 0 and self.value == 0:
				self._trigger_callback("_cb_on", event, message)
			elif event.value == 0 and self.value > 0:
				self._trigger_callback("_cb_off", event, message)
			elif event.value > 0 and self.value > 0 and self._cb_brightness_change:
				self._trigger_callback("_cb_brightness_change", event, message)
		elif event.value == "INCREASE" and self.value == 0:
			self._trigger_callback("_cb_on", event, message)
		elif event.value == "INCREASE" and self.value > 0 and self._cb_brightness_change:
			self._trigger_callback("_cb_brightness_change", event, message)
		elif event.value == "DECREASE" and self.value > 0 and self._cb_brightness_change:
			self._trigger_callback("_cb_brightness_change", event, message)
