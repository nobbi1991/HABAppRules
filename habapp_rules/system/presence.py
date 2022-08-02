"""Rule to detect presence or absence."""
import logging
import threading
import typing

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.interface
import HABApp.openhab.items
import HABApp.util

import habapp_rules.common.state_machine_rule

LOGGER = logging.getLogger("HABApp.presence")
LOGGER.setLevel("DEBUG")


# pylint: disable=no-member
class Presence(habapp_rules.common.state_machine_rule.StateMachineRule):
	"""Rules class to manage presence of a home."""

	states = [
		{"name": "presence"},
		{"name": "leaving", "timeout": 5 * 60, "on_timeout": "absence_detected"},  # leaving takes 5 minutes
		{"name": "absence", "timeout": 1.5 * 24 * 3600, "on_timeout": "long_absence_detected"},  # switch to long absence after 1.5 days
		{"name": "long_absence"}
	]

	trans = [
		{"trigger": "presence_detected", "source": ["absence", "long_absence"], "dest": "presence"},
		{"trigger": "leaving_detected", "source": "presence", "dest": "leaving"},
		{"trigger": "abort_leaving", "source": "leaving", "dest": "presence"},
		{"trigger": "absence_detected", "source": ["presence", "leaving"], "dest": "absence"},
		{"trigger": "long_absence_detected", "source": "absence", "dest": "long_absence"},
	]

	def __init__(self, name_presence: str, outside_door_names: typing.List[str], leaving_name: str, state_name: str = None, phone_names: typing.List[str] = None) -> None:
		"""Init of Presence object.

		:param name_presence: name of OpenHAB presence item
		:param outside_door_names: list of names of OpenHAB outdoor door items
		:param leaving_name: name of OpenHAB leaving item (SwitchItem)
		:param state_name: name of OpenHAB item for storing the current state (StringItem)
		:param phone_names: list of names of OpenHAB phone items
		"""
		super().__init__(state_name)

		# init items
		self.__presence_item = HABApp.openhab.items.SwitchItem.get_item(name_presence)
		self.__leaving_item = HABApp.openhab.items.SwitchItem.get_item(leaving_name)
		self.__outside_door_items = [HABApp.openhab.items.ContactItem.get_item(name) for name in outside_door_names]
		self.__phone_items = [HABApp.openhab.items.SwitchItem.get_item(name) for name in phone_names]

		# init state machine
		self.state_machine = habapp_rules.common.state_machine_rule.StateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			initial=self._get_initial_state("presence"),
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")
		super()._update_openhab_state()

		# add callbacks
		self.__leaving_item.listen_event(self._cb_leaving, HABApp.openhab.events.ItemStateChangedEventFilter())
		self.__presence_item.listen_event(self._cb_presence, HABApp.openhab.events.ItemStateChangedEventFilter())
		HABApp.util.EventListenerGroup().add_listener(self.__outside_door_items, self._cb_outside_door, HABApp.core.events.ValueChangeEventFilter()).listen()
		HABApp.util.EventListenerGroup().add_listener(self.__phone_items, self._cb_phone, HABApp.core.events.ValueChangeEventFilter()).listen()

		self.__phone_absence_timer: threading.Timer = None
		LOGGER.debug(f"Init of presence rule {self.rule_name} was successful. Initial state = {self.state}")

	def _get_initial_state(self, default_value: str) -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: return correct state if it could be detected, if not return default value
		"""
		phone_items = [phone for phone in self.__phone_items if phone.value is not None]
		if phone_items:
			if any((item.value == "ON" for item in phone_items)):
				return "presence"

			if self.__presence_item.value == "ON":
				return "leaving"
			return "absence"

		if self.__leaving_item.value == "ON":
			return "leaving"

		if self.__presence_item.value == "ON":
			return "presence"

		if self.__presence_item.value == "OFF":
			return "absence"

		return default_value

	def _update_openhab_state(self) -> None:
		"""Extend _update_openhab state of base class to also update other OpenHAB items."""
		super()._update_openhab_state()
		LOGGER.info(f"Presence state changed to {self.state}")

		# update presence item
		target_value = "ON" if self.state in {"presence", "leaving"} else "OFF"
		habapp_rules.common.helper.send_if_different(self.__presence_item.name, target_value)

		habapp_rules.common.helper.send_if_different(self.__leaving_item.name, "ON" if self.state == "leaving" else "OFF")

	def _cb_outside_door(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is called if any outside door changed state.

		:param event: state change event of door item
		"""
		if event.value == "OPEN" and self.state != "presence":
			self.presence_detected()

	def _cb_leaving(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is called if leaving item changed state.

		:param event: Item state change event of leaving item
		"""
		if event.value == "ON" and self.state == "presence":
			self.leaving_detected()
		if event.value == "OFF" and self.state == "leaving":
			self.abort_leaving()

	def _cb_presence(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is called if presence item changed state.

		:param event: Item state change event of presence item
		"""
		if event.value == "ON" and self.state in {"absence", "long_absence"}:
			self.presence_detected()
		elif event.value == "OFF" and self.state in {"presence", "leaving"}:
			self.absence_detected()

	def _cb_phone(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is called if a phone state changed.

		:param event: Item state change event of phone item
		"""
		active_phones = len([phone for phone in self.__phone_items if phone.value == "ON"])
		if active_phones == 1 and event.value == "ON":
			# first phone switched to ON
			if self.__phone_absence_timer:
				self.__phone_absence_timer.cancel()
				self.__phone_absence_timer = None

			if self.state in {"absence", "long_absence"}:
				self.presence_detected()

		elif active_phones == 0 and event.value == "OFF":
			# last phone switched to OFF
			self.__phone_absence_timer = threading.Timer(20 * 60, self.__set_leaving_through_phone)
			self.__phone_absence_timer.start()

	def __set_leaving_through_phone(self) -> None:
		"""Set leaving detected if timeout expired."""
		if self.state == "presence":
			self.leaving_detected()
		self.__phone_absence_timer = None
