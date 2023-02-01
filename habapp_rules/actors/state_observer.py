"""Implementations for observing states of switch / dimmer / roller shutter."""
from __future__ import annotations

import abc
import logging
import typing

import HABApp
import HABApp.openhab.interface
import HABApp.openhab.items

LOGGER = logging.getLogger("HABApp.actors.state_observer")
LOGGER.setLevel("DEBUG")

EventTypes = typing.Union[HABApp.openhab.events.ItemStateChangedEvent, HABApp.openhab.events.ItemCommandEvent]
CallbackType = typing.Callable[[EventTypes, str], None]


class StateObserverBase(HABApp.Rule, abc.ABC):
	"""Base class for observer classes."""

	def __init__(self, item_name: str, control_names: list[str]):
		"""Init state observer for switch item.

		:param item_name: Name of observed item
		:param control_names: list of control items
		"""
		super().__init__()

		self._last_send_value = None

		self._item = HABApp.openhab.items.OpenhabItem.get_item(item_name)

		self.__control_items = [HABApp.openhab.items.OpenhabItem.get_item(name) for name in control_names] if control_names else []
		self.__check_item_types()

		self._value = self._item.value

		self._item.listen_event(self._cb_value_change, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item.listen_event(self._cb_command, HABApp.openhab.events.ItemCommandEventFilter())
		HABApp.util.EventListenerGroup().add_listener(self.__control_items, self.__cb_control, HABApp.openhab.events.ItemCommandEventFilter()).listen()

	@property
	def value(self) -> float:
		"""Get the current brightness value of the light."""
		return self._value

	def __check_item_types(self) -> None:
		"""Check if all command and control items have the correct type.

		:raises TypeError: if one item has the wrong type"""
		target_type = type(self._item)

		wrong_types = []
		for item in self.__control_items:
			if not isinstance(item, target_type):
				wrong_types.append(f"{item.name} <{type(item).__name__}>")

		if wrong_types:
			LOGGER.error(msg := f"Found items with wrong item type. Expected: {target_type.__name__}. Wrong: {' | '.join(wrong_types)}")
			raise TypeError(msg)

	def send_command(self, value: float | str) -> None:
		"""Send brightness command to light (this should be used by rules, to not trigger a manual action)

		:param value: Value to send to the light
		:raises ValueError: if value has wrong format
		"""
		self._value = value
		self._last_send_value = value
		self._item.oh_send_command(value)

	def _cb_command(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is called if a command event of one of the command items was detected.

		:param event: event, which triggered this callback
		"""
		if event.value == self._last_send_value:
			self._last_send_value = None
		else:
			self._check_manual(event, "Manual from OpenHAB")

	def _cb_value_change(self, event: HABApp.openhab.events.ItemStateChangedEvent, call_check_manual: bool = True):
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
		self._check_manual(event, "Manual from extern")

	@abc.abstractmethod
	def _check_manual(self, event: HABApp.openhab.events.base_event.OpenhabEvent, message: str) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		:raises ValueError: if event is not supported
		"""


class StateObserverSwitch(StateObserverBase):
	"""Class to observe the on/off state of a switch item."""

	def __init__(self, item_name: str, cb_on: CallbackType, cb_off: CallbackType, control_names: list[str] = None):
		"""Init state observer for switch item.

		:param item_name: Name of switch item
		:param cb_on: callback which should be called if manual_on was detected
		:param cb_off: callback which should be called if manual_off was detected
		:param control_names: list of control items
		"""
		self.__cb_on = cb_on
		self.__cb_off = cb_off
		super().__init__(item_name, control_names)

	def _check_manual(self, event: EventTypes, message: str) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		:raises ValueError: if event is not supported
		"""
		print(f"check_manu {event.value} | {self.value}")
		if event.value != self.value:
			if event.value == "ON":
				self.__cb_on(event, message)
			elif event.value == "OFF":
				self.__cb_off(event, message)
			else:
				raise ValueError(f"Event '{event.value}' is not supported!")
			self._value = event.value

	def _cb_value_change(self, event: HABApp.openhab.events.ItemStateChangedEvent, call_check_manual: bool = True):
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		:param call_check_manual: If true: _check_manual() will be called, otherwise not. This is for dimmer lights
		"""
		if event.value != self.value:
			self._check_manual(event, "Manual from extern")
			self._value = event.value


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
		self.__expected_value: bool | None = None
		self.__cb_on = cb_on
		self.__cb_off = cb_off
		self.__cb_brightness_change = cb_brightness_change

		super().__init__(item_name, control_names)

	def send_command(self, value: float | str) -> None:
		"""Send brightness command to light (this should be used by rules, to not trigger a manual action)

		:param value: Value to send to the light
		"""
		self._last_send_value = value
		self._item.oh_send_command(value)

	def _cb_command(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is called if a command event of one of the command items was detected.

		:param event: event, which triggered this callback
		"""
		if event.value == "ON" or isinstance(event.value, (int, float)) and event.value > 0:
			self.__expected_value = True
		elif event.value == "OFF" or isinstance(event.value, (int, float)) and event.value == 0:
			self.__expected_value = False
		super()._cb_command(event)

	def _cb_value_change(self, event: HABApp.openhab.events.ItemStateChangedEvent, call_check_manual: bool = True) -> None:
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		:param call_check_manual: If true: _check_manual() will be called, otherwise not. This is used to avoid calling manual check if this class is waiting for a state update
		"""
		if event.value is None:
			return
		super()._cb_value_change(event, self.__expected_value is None)

		if self.__expected_value is True and event.value > 0:
			self.__expected_value = None
		elif self.__expected_value is False and event.value == 0:
			self.__expected_value = None

	def _check_manual(self, event: EventTypes, message: str) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		:raises ValueError: if event is not supported
		"""
		if event.value == "ON" and self.value == 0:
			self.__cb_on(event, message)
		elif event.value == "OFF" and self.value > 0:
			self.__cb_off(event, message)
		elif isinstance(event.value, (int, float)):
			if event.value > 0 and self.value == 0:
				self.__cb_on(event, message)
			elif event.value == 0 and self.value > 0:
				self.__cb_off(event, message)
			elif event.value > 0 and self.value > 0 and self.__cb_brightness_change:
				self.__cb_brightness_change(event, message)

		elif event.value == "INCREASE" and self.value == 0:
			self.__cb_on(event, message)
		elif event.value == "INCREASE" and self.value > 0 and self.__cb_brightness_change:
			self.__cb_brightness_change(event, message)

		elif event.value == "DECREASE" and self.value > 0 and self.__cb_brightness_change:
			self.__cb_brightness_change(event, message)
