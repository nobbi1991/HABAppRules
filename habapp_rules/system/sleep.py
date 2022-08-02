"""Rule to set/unset sleep state."""
import logging

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.interface
import HABApp.openhab.items
import HABApp.util

import habapp_rules.common.state_machine_rule
import habapp_rules.common.helper

LOGGER = logging.getLogger("HABApp.sleep")
LOGGER.setLevel("DEBUG")


# pylint: disable=no-member
class Sleep(habapp_rules.common.state_machine_rule.StateMachineRule):
	"""Rules class to manage sleep state."""

	states = [
		{"name": "awake"},
		{"name": "pre_sleeping", "timeout": 3, "on_timeout": "pre_sleeping_timeout"},
		{"name": "sleeping"},
		{"name": "post_sleeping", "timeout": 3, "on_timeout": "post_sleeping_timeout"},
		{"name": "locked"},
	]

	trans = [
		{"trigger": "start_sleeping", "source": "awake", "dest": "pre_sleeping"},
		{"trigger": "pre_sleeping_timeout", "source": "pre_sleeping", "dest": "sleeping"},
		{"trigger": "end_sleeping", "source": "sleeping", "dest": "post_sleeping"},
		{"trigger": "end_sleeping", "source": "pre_sleeping", "dest": "awake", "unless": "lock_request_active"},
		{"trigger": "end_sleeping", "source": "pre_sleeping", "dest": "locked", "conditions": "lock_request_active"},
		{"trigger": "post_sleeping_timeout", "source": "post_sleeping", "dest": "awake", "unless": "lock_request_active"},
		{"trigger": "post_sleeping_timeout", "source": "post_sleeping", "dest": "locked", "conditions": "lock_request_active"},
		{"trigger": "set_lock", "source": "awake", "dest": "locked"},
		{"trigger": "release_lock", "source": "locked", "dest": "awake"}
	]

	def __init__(self, name_sleep: str, name_sleep_request: str, state_name: str = None, name_lock: str = None, name_lock_request: str = None, name_display_text: str = None) -> None:
		"""Init of Sleep object.

		:param name_sleep: name of OpenHAB sleep item (SwitchItem)
		:param name_sleep_request: name of OpenHAB sleep request item (SwitchItem)
		:param state_name: name of OpenHAB item for storing the current state (StringItem)
		:param name_lock: name of OpenHAB lock item (SwitchItem)
		:param name_lock_request: name of OpenHAB lock request item (SwitchItem)
		:param name_display_text: name of OpenHAB display text item (StringItem)
		"""
		super().__init__(state_name)

		# init items
		self.__item_sleep = HABApp.openhab.items.SwitchItem.get_item(name_sleep)
		self.__item_sleep_request = HABApp.openhab.items.SwitchItem.get_item(name_sleep_request)
		self.__item_lock = HABApp.openhab.items.SwitchItem.get_item(name_lock) if name_lock else None
		self.__item_lock_request = HABApp.openhab.items.SwitchItem.get_item(name_lock_request) if name_lock_request else None
		self.__item_display_text = HABApp.openhab.items.StringItem.get_item(name_display_text) if name_display_text else None

		# init attributes
		self._sleep_request_active = bool(self.__item_sleep_request)
		self._lock_request_active = bool(self.__item_lock_request) if self.__item_lock_request is not None else False

		# init state machine
		self.state_machine = habapp_rules.common.state_machine_rule.StateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			initial=self._get_initial_state("awake"),
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")
		super()._update_openhab_state()

		self._update_openhab_state()

		# add callbacks
		self.__item_sleep_request.listen_event(self._cb_sleep_request, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self.__item_lock_request is not None:
			self.__item_lock_request.listen_event(self._cb_lock_request, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _get_initial_state(self, default_value: str) -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: return correct state if it could be detected, if not return default value
		"""
		sleep_req = bool(self.__item_sleep_request) if self.__item_sleep_request.value is not None else None
		lock_req = bool(self.__item_lock_request) if self.__item_lock_request is not None and self.__item_lock_request.value is not None else None

		if sleep_req:
			return "sleeping"
		if lock_req:
			return "locked"
		if sleep_req is False:
			return "awake"

		return default_value

	@property
	def sleep_request_active(self) -> bool:
		"""Check if a lock request is active

		:return: return true if lock request is active
		"""
		return self._sleep_request_active

	@property
	def lock_request_active(self) -> bool:
		"""Check if a lock request is active

		:return: return true if lock request is active
		"""
		return self._lock_request_active

	def _update_openhab_state(self):
		"""Extend _update_openhab state of base class to also update other OpenHAB items."""
		super()._update_openhab_state()

		# update sleep state
		if self.state in {"pre_sleeping", "sleeping"}:
			habapp_rules.common.helper.send_if_different(self.__item_sleep.name, "ON")
		else:
			habapp_rules.common.helper.send_if_different(self.__item_sleep.name, "OFF")

		# update lock state
		self.__update_lock_state()

		# update display text
		if self.__item_display_text is not None:
			self.__item_display_text.oh_send_command(self.__get_display_text())

	def __get_display_text(self) -> str:
		"""Get Text for displays.

		:return: display text
		"""
		if self.state == "awake":
			return "Schlafen"
		if self.state == "pre_sleeping":
			return "Guten Schlaf"
		if self.state == "sleeping":
			return "Aufstehen"
		if self.state == "post_sleeping":
			return "Guten Morgen"
		if self.state == "locked":
			return "Gesperrt"
		return ""

	def __update_lock_state(self):
		"""Update the return lock state value of OpenHAB item."""
		if self.__item_lock is not None:
			if self.state in {"pre_sleeping", "post_sleeping", "locked"}:
				habapp_rules.common.helper.send_if_different(self.__item_lock.name, "ON")
			else:
				habapp_rules.common.helper.send_if_different(self.__item_lock.name, "OFF")

	def _cb_sleep_request(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		"""Callback, which is called if sleep request item changed state.

		:param event: Item state change event of sleep_request item
		"""
		if event.value == "ON" and self.state == "awake":
			self._sleep_request_active = True
			self.start_sleeping()
		elif event.value == "ON" and self.state == "locked":
			self._sleep_request_active = False
			self.__item_sleep_request.oh_send_command("OFF")
		elif event.value == "OFF" and self.state in {"sleeping", "pre_sleeping"}:
			self._sleep_request_active = True
			self.end_sleeping()

	def _cb_lock_request(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		"""Callback, which is called if lock request item changed state.

		:param event: Item state change event of sleep_request item
		"""
		self._lock_request_active = event.value == "ON"

		if self.state == "awake" and event.value == "ON":
			self.set_lock()
		elif self.state == "locked" and event.value == "OFF":
			self.release_lock()
		else:
			self.__update_lock_state()
