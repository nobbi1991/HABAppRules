"""Implementations for observing states of switch / dimmer / roller shutter."""
from __future__ import annotations

import abc
import logging
import threading
import time
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

	def __init__(self, item_name: str, additional_command_names: list[str], control_names: list[str], expected_value_types: tuple):
		"""Init state observer for switch item.

		:param item_name: Name of observed item
		:param additional_command_names: list of additional command items # todo: check if needed
		:param control_names: list of control items
		:param expected_value_types: expected value type of observed item
		"""
		super().__init__()

		self.__expected_value_types = expected_value_types
		self._send_commands = []

		self._item = HABApp.openhab.items.OpenhabItem.get_item(item_name)

		self.__command_items = [HABApp.openhab.items.OpenhabItem.get_item(name) for name in additional_command_names] if additional_command_names else []
		self.__control_items = [HABApp.openhab.items.OpenhabItem.get_item(name) for name in control_names] if control_names else []
		self.__check_item_types()

		self._value = self._item.value

		self._item.listen_event(self._cb_value_change, HABApp.openhab.events.ItemStateEventFilter())
		HABApp.util.EventListenerGroup().add_listener(self.__command_items + [self._item], self.__cb_command, HABApp.openhab.events.ItemCommandEventFilter()).listen()
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
		for item in self.__command_items + self.__control_items:
			if not isinstance(item, target_type):
				wrong_types.append(f"{item.name} <{type(item).__name__}>")

		if wrong_types:
			LOGGER.error(msg := f"Found items with wrong item type. Expected: {target_type.__name__}. Wrong: {' | '.join(wrong_types)}")
			raise TypeError(msg)

	def send_command(self, value: float | str) -> None:
		"""Send brightness command to light (this should be used by rules, to not trigger a manual action)

		:param value: Value to send to the light
		"""
		if isinstance(value, self.__expected_value_types):
			self._value = value
		self._send_commands.append(value)
		self._item.oh_send_command(value)

	def __cb_command(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is called if a command event of one of the command items was detected.

		:param event: event, which triggered this callback
		"""
		if event.value in self._send_commands:
			self._send_commands.remove(event.value)
		else:
			self._check_manual(event, "Manual from OpenHAB")

	def _cb_value_change(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		"""
		self._check_manual(event, "Manual from extern")

		if isinstance(value := event.value, self.__expected_value_types):
			self._value = value

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
		"""


class StateObserverSwitch(StateObserverBase):
	"""Class to observe the on/off state of a switch item."""

	def __init__(self, item_name: str, cb_on: CallbackType, cb_off: CallbackType, additional_command_names: list[str] = None, control_names: list[str] = None):
		"""Init state observer for switch item.

		:param item_name: Name of switch item
		:param cb_on: callback which should be called if manual_on was detected
		:param cb_off: callback which should be called if manual_off was detected
		:param additional_command_names: list of additional command items # todo: check if needed
		:param control_names: list of control items
		"""
		self.__cb_on = cb_on
		self.__cb_off = cb_off
		super().__init__(item_name, additional_command_names, control_names, expected_value_types=(str,))

	def _check_manual(self, event: EventTypes, message: str):
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		"""
		if event.value != self.value:
			if event.value == "ON":
				self.__cb_on(event, message)
			elif event.value == "OFF":
				self.__cb_off(event, message)
			self._value = event.value

	def _cb_value_change(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		"""Callback, which is called if a value change of the light item was detected.

		:param event: event, which triggered this callback
		"""
		if event.value != self.value:
			self._check_manual(event, "Manual from extern")
			self._value = event.value


class StateObserverDimmer(StateObserverBase):
	"""Class to observe the on/off state of a dimmer item."""

	def __init__(self, item_name: str, cb_on: CallbackType, cb_off: CallbackType, additional_command_names: list[str] = None, control_names: list[str] = None):
		"""Init state observer for dimmer item.

		:param item_name: Name of dimmer item
		:param cb_on: callback which should be called if manual_on was detected
		:param cb_off: callback which should be called if manual_off was detected
		:param additional_command_names: list of additional command items # todo: check if needed
		:param control_names: list of control items
		"""
		self.__cb_on = cb_on
		self.__cb_off = cb_off
		self.__wait_after_decrease_thread: threading.Thread | None = None
		self.__wait_after_decrease_active = False
		self.__last_received_value = None

		super().__init__(item_name, additional_command_names, control_names, expected_value_types=(int, float))

	def __check_different_value(self, new_value: float | str) -> bool:
		"""Check if new value is different from last value.

		:param new_value: new value from state
		:return: True if value is different or INCREASE/DECREASE, else False
		"""
		if new_value in {"INCREASE", "DECREASE"}:
			# Increase / decrease are no states, but always have to be checked by check_manual
			return True

		state_is_different = False

		if self.__last_received_value is None:
			# first call (initial state)
			state_is_different = True
		elif new_value in {"OFF", 0}:
			if isinstance(self.__last_received_value, str) and self.__last_received_value == "ON" or isinstance(self.__last_received_value, (int, float)) and self.__last_received_value > 0:
				# value change from OFF to ON
				state_is_different = True
		elif self.__last_received_value in {"OFF", 0}:
			# value changed from ON to OFF
			state_is_different = True

		self.__last_received_value = new_value
		return state_is_different

	def _check_manual(self, event: EventTypes, message: str) -> None:
		"""Check if light was triggered by a manual action

		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		"""
		self.__wait_after_decrease_active = False  # cancel timer

		if not self.__check_different_value(event.value):
			return

		if event.value == "ON":
			self.__cb_on(event, message)
		elif event.value == "OFF":
			self.__cb_off(event, message)
		elif isinstance(event.value, (int, float)):
			if event.value > 0 and self.value == 0:
				self.__cb_on(event, message)
			elif event.value == 0 and self.value > 0:
				self.__cb_off(event, message)

		elif event.value == "INCREASE" and self.value == 0:
			self.__cb_on(event, message)

		elif event.value == "DECREASE":
			self.__wait_after_decrease_thread = threading.Thread(target=self.__check_decrease_switched_off, args=(15, event, message))
			self.__wait_after_decrease_active = True
			self.__wait_after_decrease_thread.start()

	def __check_decrease_switched_off(self, timeout: int, event: EventTypes, message: str) -> None:
		"""Check if light is switched off by DECREASE command. This must run in a separate thread

		:param timeout: timeout in seconds to wait for value 0
		:param event: event which triggered this method. This will be forwarded to the callback
		:param message: message to forward to the callback
		"""
		initial_value = self.value

		for _ in range(timeout * 10):
			if not self.__wait_after_decrease_active:
				break
			if (new_value := self.value) != initial_value:
				if new_value == 0:
					self.__cb_off(event, message)
				break
			time.sleep(0.1)
