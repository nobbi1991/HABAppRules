"""Rule to set/unset sleep state."""
import datetime
import logging

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.items
import HABApp.util

import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule

LOGGER = logging.getLogger(__name__)


# pylint: disable=no-member
class Sleep(habapp_rules.core.state_machine_rule.StateMachineRule):
	"""Rules class to manage sleep state.

	Example OpenHAB configuration:
	# KNX-things:
	Thing device T00_99_OpenHab_Sleep "KNX OpenHAB Sleep"{
        Type switch             : sleep             "Sleep Request"             [ ga="0/2/30"]
        Type switch-control     : sleep_RM          "Sleep RM"                  [ ga="0/2/31"]

        Type switch             : sleep_lock        "Sleep Lock Request"        [ ga="0/2/32"]
        Type switch-control     : sleep_lock_RM     "Sleep Lock RM"             [ ga="0/2/33"]

        Type string-control     : sleep_text        "Sleep Text"                [ ga="16.000:0/2/34"]
    }

    # Items:
    Switch    I01_02_Sleep              "Sleep [%s]"                <moon>     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep_RM"}
	Switch    I01_02_Sleep_req          "Sleep request"             <moon>     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep"}
	String    I01_02_Sleep_text         "Text for display [%s]"                {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep_text"}
	Switch    I01_02_Sleep_lock         "Lock [%s]"                 <lock>     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep_lock_RM"}
	Switch    I01_02_Sleep_lock_req     "Lock request"              <lock>     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep_lock"}
	String    I01_02_Sleep_State        "State [%s]"                <state>

	# Rule init:
	habapp_rules.system.sleep.Sleep("I01_02_Sleep","I01_02_Sleep_req", "I01_02_Sleep_State", "I01_02_Sleep_lock", "I01_02_Sleep_lock_req", "I01_02_Sleep_text")
	"""

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

	def __init__(self, name_sleep: str, name_sleep_request: str, name_lock: str = None, name_lock_request: str = None, name_display_text: str = None, name_state: str = None, state_label: str = "Sleep state") -> None:
		"""Init of Sleep object.

		:param name_sleep: name of OpenHAB sleep item (SwitchItem)
		:param name_sleep_request: name of OpenHAB sleep request item (SwitchItem)
		:param name_lock: name of OpenHAB lock item (SwitchItem)
		:param name_lock_request: name of OpenHAB lock request item (SwitchItem)
		:param name_display_text: name of OpenHAB display text item (StringItem)
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		"""
		if not name_state:
			name_state = f"H_Sleep_{name_sleep}_state"
		habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, name_state, state_label)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_sleep)

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
		self.state_machine = habapp_rules.core.state_machine_rule.StateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")
		self._set_initial_state()

		self._update_openhab_state()

		# add callbacks
		self.__item_sleep_request.listen_event(self._cb_sleep_request, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self.__item_lock_request is not None:
			self.__item_lock_request.listen_event(self._cb_lock_request, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._instance_logger.debug(super().get_initial_log_message())

	def _get_initial_state(self, default_value: str = "awake") -> str:
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
		"""Check if a sleep request is active

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
			habapp_rules.core.helper.send_if_different(self.__item_sleep.name, "ON")
		else:
			habapp_rules.core.helper.send_if_different(self.__item_sleep.name, "OFF")

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
				habapp_rules.core.helper.send_if_different(self.__item_lock.name, "ON")
			else:
				habapp_rules.core.helper.send_if_different(self.__item_lock.name, "OFF")

	def _cb_sleep_request(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		"""Callback, which is called if sleep request item changed state.

		:param event: Item state change event of sleep_request item
		"""
		if event.value == "ON" and self.state == "awake":
			self._instance_logger.debug("Start sleeping through sleep switch")
			self._sleep_request_active = True
			self.start_sleeping()
		elif event.value == "ON" and self.state == "locked":
			self._sleep_request_active = False
			self.__item_sleep_request.oh_send_command("OFF")
		elif event.value == "OFF" and self.state in {"sleeping", "pre_sleeping"}:
			self._instance_logger.debug("End sleeping through sleep switch")
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


class LinkSleep(HABApp.Rule):
	"""Link sleep items depending on current time"""

	def __init__(self, sleep_master_name: str, sleep_req_slave_names: list[str], link_active_time_start: datetime.time = datetime.time(0), link_active_time_end: datetime.time = datetime.time(23, 59), link_active_name: str | None = None) -> None:
		"""Init rule.

		:param sleep_master_name: Name of OpenHAB switch item for master sleep item
		:param sleep_req_slave_names: Names of OpenHAB switch items for request sleep for slaves
		:param link_active_time_start: Start time when the linking is active
		:param link_active_time_end: End time when the linking is not active anymore
		:param link_active_name: Name of OpenHAB switch item for feedback if link is active
		"""
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self.rule_name)

		self._item_master = HABApp.openhab.items.SwitchItem.get_item(sleep_master_name)
		self._items_slaves = [HABApp.openhab.items.SwitchItem.get_item(item_name) for item_name in sleep_req_slave_names]
		self._item_link_active = HABApp.openhab.items.SwitchItem.get_item(link_active_name) if link_active_name else None

		self._start_time = link_active_time_start
		self._end_time = link_active_time_end

		self._item_master.listen_event(self._cb_master, HABApp.openhab.events.ItemStateChangedEventFilter())

		if self._item_link_active is not None:
			self.run.at(self._start_time, self._set_link_active_feedback, target_state="ON")
			self.run.at(self._end_time, self._set_link_active_feedback, target_state="OFF")
			self.run.soon(self._set_link_active_feedback, target_state=self._check_time_in_window())

	def _check_time_in_window(self) -> bool:
		"""Check if current time is in the active time window

		:return: True if current time is in time the active time window
		"""
		now = datetime.datetime.now().time()

		if self._start_time <= self._end_time:
			return self._start_time <= now <= self._end_time
		# cross midnight
		return self._start_time <= now or now <= self._end_time

	def _cb_master(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if the state of the master item changes

		:param event: state change event
		"""
		if not self._check_time_in_window():
			return

		self._instance_logger.debug(f"Set request of all linked sleep states of {self._item_master.name}")
		for itm in self._items_slaves:
			habapp_rules.core.helper.send_if_different(itm, event.value)

	def _set_link_active_feedback(self, target_state: str) -> None:
		"""Set feedback for link is active.

		:param target_state: Target state which should be set ["ON" / "OFF"]
		"""
		self._item_link_active.oh_send_command(target_state)
