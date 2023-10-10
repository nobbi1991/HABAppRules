"""Rules to manage shading objects."""
import abc
import logging

import HABApp

import habapp_rules.actors.config.shading
import habapp_rules.actors.state_observer
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system

LOGGER = logging.getLogger(__name__)


# pylint: disable=no-member, too-many-instance-attributes
class _ShadingBase(habapp_rules.core.state_machine_rule.StateMachineRule):
	"""Base class for shading objects."""

	states = [
		{"name": "WindAlarm"},
		{"name": "Manual"},
		{"name": "Hand", "timeout": 20 * 3600, "on_timeout": "_auto_hand_timeout"},
		{"name": "Auto", "initial": "Init", "children": [
			{"name": "Init"},
			{"name": "Open"},
			{"name": "DoorOpen", "initial": "Open", "children": [
				{"name": "Open"},
				{"name": "PostOpen", "timeout": 5 * 60, "on_timeout": "_timeout_post_door_open"}
			]},
			{"name": "NightClose"},
			{"name": "SleepingClose"},
			{"name": "SunProtection"},
		]}
	]

	trans = [
		# wind alarm
		{"trigger": "_wind_alarm_on", "source": ["Auto", "Hand", "Manual"], "dest": "WindAlarm"},
		{"trigger": "_wind_alarm_off", "source": "WindAlarm", "dest": "Manual", "conditions": "_manual_active"},
		{"trigger": "_wind_alarm_off", "source": "WindAlarm", "dest": "Auto", "unless": "_manual_active"},

		# manual
		{"trigger": "_manual_on", "source": ["Auto", "Hand"], "dest": "Manual"},
		{"trigger": "_manual_off", "source": "Manual", "dest": "Auto"},

		# hand
		{"trigger": "_hand_command", "source": ["Auto"], "dest": "Hand"},
		{"trigger": "_auto_hand_timeout", "source": "Hand", "dest": "Auto"},

		# sun
		{"trigger": "_sun_on", "source": "Auto_Open", "dest": "Auto_SunProtection"},
		{"trigger": "_sun_off", "source": "Auto_SunProtection", "dest": "Auto_Open"},

		# sleep
		{"trigger": "_sleep_started", "source": ["Auto_Open", "Auto_NightClose", "Auto_SunProtection"], "dest": "Auto_SleepingClose"},
		{"trigger": "_sleep_started", "source": "Hand", "dest": "Auto"},
		{"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_SunProtection", "conditions": "_sun_protection_active_and_configured"},
		{"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_NightClose", "conditions": ["_night_active_and_configured"]},
		{"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_Open", "unless": ["_night_active_and_configured", "_sun_protection_active_and_configured"]},

		# door
		{"trigger": "_door_open", "source": ["Auto_NightClose", "Auto_SunProtection", "Auto_SleepingClose", "Auto_Open"], "dest": "Auto_DoorOpen"},
		{"trigger": "_door_open", "source": "Auto_DoorOpen_PostOpen", "dest": "Auto_DoorOpen_Open"},
		{"trigger": "_door_closed", "source": "Auto_DoorOpen_Open", "dest": "Auto_DoorOpen_PostOpen"},
		{"trigger": "_timeout_post_door_open", "source": "Auto_DoorOpen_PostOpen", "dest": "Auto_Init"},

		# night close
		{"trigger": "_night_started", "source": ["Auto_Open", "Auto_SunProtection"], "dest": "Auto_NightClose", "conditions": "_night_active_and_configured"},
		{"trigger": "_night_stopped", "source": "Auto_NightClose", "dest": "Auto_SunProtection", "conditions": "_sun_protection_active_and_configured"},
		{"trigger": "_night_stopped", "source": "Auto_NightClose", "dest": "Auto_Open", "unless": ["_sun_protection_active_and_configured"]}

	]
	_item_shading_position: HABApp.openhab.items.rollershutter_item.RollershutterItem | HABApp.openhab.items.dimmer_item.DimmerItem
	_state_observer_pos: habapp_rules.actors.state_observer.StateObserverRollerShutter | habapp_rules.actors.state_observer.StateObserverDimmer

	# pylint: disable=too-many-arguments
	def __init__(self,
	             name_shading_position: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.shading.ShadingConfig,
	             shading_position_control_names: list[str] | None = None,
	             shading_position_group_names: list[str] | None = None,
	             name_wind_alarm: str | None = None,
	             name_sun_protection: str | None = None,
	             name_sleeping_state: str | None = None,
	             name_night: str | None = None,
	             name_door: str | None = None,
	             name_summer: str | None = None,
	             name_hand_manual_is_active_feedback: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of _ShadingBase.

		:param name_shading_position:  name of OpenHAB shading item (RollershutterItem | DimmerItem)
		:param name_manual: name of OpenHAB switch item to disable all automatic functions
		:param config: configuration of the shading object
		:param shading_position_control_names: [optional] list of control items.
		:param shading_position_group_names: [optional]  list of group items where the item is a part of. Group item type must match with type of item_name
		:param name_wind_alarm: [optional] name of OpenHAB switch item which is 'ON' when wind-alarm is active
		:param name_sun_protection: [optional] name of OpenHAB switch item which is 'ON' when sun protection is active
		:param name_sleeping_state: [optional] name of OpenHAB sleeping state item (StringItem)
		:param name_night: [optional] name of OpenHAB switch item which is 'ON' when it is dark and 'OFF' when it is bright
		:param name_door: [optional] name of OpenHAB door item (ContactItem)
		:param name_summer: [optional] name of OpenHAB switch item which is 'ON' during summer and 'OFF' during winter
		:param name_hand_manual_is_active_feedback: [optional] name of OpenHAB switch item which is 'ON' if state is manual or hand
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: [optional] label of OpenHAB item for storing the current state (StringItem)
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if given config / items are not valid
		"""
		self._config = config

		if not name_state:
			name_state = f"H_{name_shading_position}_state"
		habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, name_state, state_label)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_shading_position)

		# init items
		self._item_shading_position = HABApp.openhab.items.base_item.OpenhabItem.get_item(name_shading_position)
		self._item_manual = HABApp.openhab.items.switch_item.SwitchItem.get_item(name_manual)
		self._item_wind_alarm = HABApp.openhab.items.switch_item.SwitchItem.get_item(name_wind_alarm) if name_wind_alarm else None
		self._item_sun_protection = HABApp.openhab.items.switch_item.SwitchItem.get_item(name_sun_protection) if name_sun_protection else None
		self._item_sleeping_state = HABApp.openhab.items.string_item.StringItem.get_item(name_sleeping_state) if name_sleeping_state else None
		self._item_night = HABApp.openhab.items.switch_item.SwitchItem.get_item(name_night) if name_night else None
		self._item_door = HABApp.openhab.items.contact_item.ContactItem.get_item(name_door) if name_door else None
		self._item_summer = HABApp.openhab.items.switch_item.SwitchItem.get_item(name_summer) if name_summer else None
		self._item_hand_manual_is_active_feedback = HABApp.openhab.items.switch_item.SwitchItem.get_item(name_hand_manual_is_active_feedback) if name_hand_manual_is_active_feedback else None

		# init state machine
		self._previous_state = None
		self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")
		self._set_initial_state()
		self._check_config()
		self._apply_config()

		self._position_before: habapp_rules.actors.config.shading.ShadingPosition = habapp_rules.actors.config.shading.ShadingPosition(self._item_shading_position.value)

		if isinstance(self._item_shading_position, HABApp.openhab.items.rollershutter_item.RollershutterItem):
			self._state_observer_pos = habapp_rules.actors.state_observer.StateObserverRollerShutter(name_shading_position, self._cb_hand, shading_position_control_names, shading_position_group_names)
		elif isinstance(self._item_shading_position, HABApp.openhab.items.dimmer_item.DimmerItem):
			self._state_observer_pos = habapp_rules.actors.state_observer.StateObserverDimmer(name_shading_position, self._cb_hand, self._cb_hand, self._cb_hand, shading_position_control_names, shading_position_group_names)
		else:
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"shading position item must be a dimmer or roller-shutter item. Given type: {type(self._item_shading_position)}")

		# callbacks
		self._item_manual.listen_event(self._cb_manual, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_wind_alarm is not None:
			self._item_wind_alarm.listen_event(self._cb_wind_alarm, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_sun_protection is not None:
			self._item_sun_protection.listen_event(self._cb_sun, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_sleeping_state is not None:
			self._item_sleeping_state.listen_event(self._cb_sleep_state, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_night is not None:
			self._item_night.listen_event(self._cb_night, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_door is not None:
			self._item_door.listen_event(self._cb_door, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._update_openhab_state()

	def _check_config(self):
		"""Check if config can be applied with the given items.

		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if given config / items are not valid
		"""
		if self._config.pos_night_close_summer is not None and self._item_summer is None:
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("Night close position is set for summer, but item for summer / winter is missing!")

	def _apply_config(self) -> None:
		"""Apply config to state machine."""
		# set timeouts
		self.state_machine.states["Auto"].states["DoorOpen"].states["PostOpen"].timeout = self._config.door_post_time
		self.state_machine.states["Manual"].timeout = self._config.manual_timeout

	def _get_initial_state(self, default_value: str = "") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		if self._item_wind_alarm:
			return "WindAlarm"
		if self._item_manual:
			return "Manual"
		if self._item_door is not None and self._item_door.is_open():  # self._item_door.is_open():
			return "Auto_DoorOpen_Open"
		if self._item_sleeping_state in (habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value):
			return "Auto_SleepingClose"
		if self._item_night and self._night_active_and_configured():
			return "Auto_NightClose"
		if self._sun_protection_active_and_configured():
			return "Auto_SunProtection"
		return "Auto_Open"

	def _update_openhab_state(self) -> None:
		"""Update OpenHAB state item and other states.

		This method should be set to "after_state_change" of the state machine.
		"""
		if self.state != self._previous_state:
			super()._update_openhab_state()
			self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

			self._set_shading_state()

			if self._item_hand_manual_is_active_feedback is not None:
				self._item_hand_manual_is_active_feedback.oh_post_update("ON" if self.state in {"Manual", "Hand"} else "OFF")

			self._previous_state = self.state

	@abc.abstractmethod
	def _set_shading_state(self) -> None:
		"""Set shading state"""

	def _get_target_position(self) -> habapp_rules.actors.config.shading.ShadingPosition | None:
		"""Get target position for shading object.

		:return: target shading position
		"""

		if self.state in {"Hand", "Manual"}:
			if self._previous_state == "WindAlarm":
				return self._position_before
			return None

		if self.state == "WindAlarm":
			return self._config.pos_wind_alarm

		if self.state == "Auto_Open":
			return self._config.pos_auto_open

		if self.state == "Auto_SunProtection":
			return self._config.pos_sun_protection

		if self.state == "Auto_SleepingClose":
			return self._config.pos_sleeping

		if self.state == "Auto_NightClose":
			if bool(self._item_summer):
				return self._config.pos_night_close_summer
			return self._config.pos_night_close_winter

		if self.state == "Auto_DoorOpen_Open":
			return self._config.pos_door_open

		return None

	def on_enter_Auto_Init(self) -> None:  # pylint: disable=invalid-name
		"""Is called on entering of init state"""
		self._set_initial_state()

	def on_exit_Manual(self) -> None:  # pylint: disable=invalid-name
		"""Is called if state Manual is left."""
		self._set_position_before()

	def on_exit_Hand(self) -> None:  # pylint: disable=invalid-name
		"""Is called if state Hand is left."""
		self._set_position_before()

	def _set_position_before(self) -> None:
		"""Set / save position before manual state is entered. This is used to restore the previous position"""
		self._position_before = habapp_rules.actors.config.shading.ShadingPosition(self._item_shading_position.value)

	def _manual_active(self) -> bool:
		"""Check if manual is active.

		:return: True if night is active
		"""
		return bool(self._item_manual)

	def _sun_protection_active_and_configured(self) -> bool:
		"""Check if sun protection is active.

		:return: True if night is active
		"""
		return bool(self._item_sun_protection) and self._config.pos_sun_protection is not None

	def _night_active_and_configured(self) -> bool:
		"""Check if night is active and configured.

		:return: True if night is active
		"""
		night_config = self._config.pos_night_close_summer if bool(self._item_summer) else self._config.pos_night_close_winter
		return bool(self._item_night) and night_config is not None

	def _cb_hand(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if a external control was detected.

		:param event: original trigger event
		"""
		self._hand_command()

	def _cb_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if manual mode changed.

		:param event: original trigger event
		"""
		if event.value == "ON":
			self._manual_on()
		else:
			self._manual_off()

	def _cb_wind_alarm(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if wind alarm changed.

		:param event: original trigger event
		"""
		if event.value == "ON":
			self._wind_alarm_on()
		else:
			self._wind_alarm_off()

	def _cb_sun(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if sun state changed.

		:param event: original trigger event
		"""
		if event.value == "ON":
			self._sun_on()
		else:
			self._sun_off()

	def _cb_sleep_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if sleeping state changed.

		:param event: original trigger event
		"""
		if event.value == habapp_rules.system.SleepState.PRE_SLEEPING.value:
			self._sleep_started()
		elif event.value == habapp_rules.system.SleepState.POST_SLEEPING.value:
			self._sleep_stopped()

	def _cb_night(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if night / dark state changed.

		:param event: original trigger event
		"""
		if event.value == "ON":
			self._night_started()
		else:
			self._night_stopped()

	def _cb_door(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if door state changed.

		:param event: original trigger event
		"""
		if event.value == "OPEN":
			self._door_open()
		else:
			self._door_closed()


class Shutter(_ShadingBase):
	"""Rules class to manage a normal shutters (or curtains).

			# KNX-things:
			Thing device KNX_Shading "KNX OpenHAB dimmer observer"{
				Type dimmer                 : shading_position          "Shading position"          [ position="5.001:4/1/12+<4/1/15" ]
	            Type dimmer-control         : shading_position_ctr      "Shading position ctr"      [ position="5.001:4/1/12+<4/1/15" ]
				Type dimmer-control         : shading_group_all_ctr     "Shading all ctr"           [ position="5.001:4/1/112+<4/1/115""]
				Type switch-control         : shading_hand_manual_ctr   "Shading hand / manual"     [ ga="4/1/20" ]
			}

			# Items:
			Rollershutter    shading_position       "Shading position [%s %%]"          <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_position"}
			Rollershutter    shading_position_ctr   "Shading position ctr [%s %%]"      <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_position_ctr"}
			Switch           shading_manual         "Shading manual"
			Rollershutter    shading_all_ctr        "Shading all ctr [%s %%]"           <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_group_all_ctr"}
			Switch           shading_hand_manual    "Shading in Hand / Manual state"                        {channel="knx:device:bridge:KNX_Shading:shading_hand_manual_ctr"}


			# Rule init:
			habapp_rules.actors.shading.Shutter(
				"shading_position",
				"shading_manual",
				habapp_rules.actors.config.shading.CONFIG_DEFAULT,
				["shading_position_ctr", "shading_all_ctr"],
				[],
				"I99_99_WindAlarm",
				"I99_99_SunProtection",
				"I99_99_Sleeping_State",
				"I99_99_Night",
				"I99_99_Door",
				"I99_99_Summer"
				"shading_hand_manual"
			)
			"""

	# pylint: disable=too-many-arguments,too-many-locals
	def __init__(self,
	             name_shading_position: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.shading.ShadingConfig,
	             shading_position_control_names: list[str] | None = None,
	             shading_position_group_names: list[str] | None = None,
	             name_wind_alarm: str | None = None,
	             name_sun_protection: str | None = None,
	             name_sleeping_state: str | None = None,
	             name_night: str | None = None,
	             name_door: str | None = None,
	             name_summer: str | None = None,
	             name_hand_manual_is_active_feedback: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of Raffstore object.

		:param name_shading_position: name of OpenHAB shading item (RollershutterItem)
		:param name_manual: name of OpenHAB switch item to disable all automatic functions
		:param config: configuration of the shading object
		:param shading_position_control_names: [optional] list of control items.
		:param shading_position_group_names: [optional]  list of group items where the item is a part of. Group item type must match with type of item_name
		:param name_wind_alarm: [optional] name of OpenHAB switch item which is 'ON' when wind-alarm is active
		:param name_sun_protection: [optional] name of OpenHAB switch item which is 'ON' when sun protection is active
		:param name_sleeping_state: [optional] name of OpenHAB sleeping state item (StringItem)
		:param name_night: [optional] name of OpenHAB switch item which is 'ON' when it is dark and 'OFF' when it is bright
		:param name_door: [optional] name of OpenHAB door item (ContactItem)
		:param name_summer: [optional] name of OpenHAB switch item which is 'ON' during summer and 'OFF' during winter
		:param name_hand_manual_is_active_feedback: [optional] name of OpenHAB switch item which is 'ON' if state is manual or hand
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: [optional] label of OpenHAB item for storing the current state (StringItem)
		"""
		_ShadingBase.__init__(
			self,
			name_shading_position,
			name_manual,
			config,
			shading_position_control_names,
			shading_position_group_names,
			name_wind_alarm, name_sun_protection,
			name_sleeping_state,
			name_night, name_door,
			name_summer,
			name_hand_manual_is_active_feedback,
			name_state,
			state_label
		)

		self._instance_logger.debug(self.get_initial_log_message())

	def _set_shading_state(self) -> None:
		"""Set shading state"""
		if self._previous_state is None:
			# don't change value if called during init (_previous_state == None)
			return

		target_position = self._get_target_position()

		if target_position is None:
			return

		if (position := target_position.position) is not None:
			self._state_observer_pos.send_command(position)
			self._instance_logger.debug(f"set position {target_position.position}")


# pylint: disable=too-many-arguments
class Raffstore(_ShadingBase):
	"""Rules class to manage a raffstore.

		# KNX-things:
		Thing device KNX_Shading "KNX OpenHAB dimmer observer"{
			Type rollershutter          : shading_position          "Shading position"          [ upDown="4/1/10", stopMove="4/1/11", position="5.001:4/1/12+<4/1/15" ]
            Type rollershutter-control  : shading_position_ctr      "Shading position ctr"      [ upDown="4/1/10", stopMove="4/1/11" ]
            Type dimmer                 : shading_slat              "Shading slat"              [ position="5.001:4/1/13+<4/1/16" ]
			Type rollershutter-control  : shading_group_all_ctr     "Shading all ctr"           [ upDown="4/1/110", stopMove="4/1/111"]
			Type switch-control         : shading_hand_manual_ctr   "Shading hand / manual"     [ ga="4/1/20" ]
		}

		# Items:
		Rollershutter    shading_position       "Shading position [%s %%]"          <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_position"}
		Rollershutter    shading_position_ctr   "Shading position ctr [%s %%]"      <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_position_ctr"}
		Dimmer           shading_slat           "Shading slat [%s %%]"              <slat>              {channel="knx:device:bridge:KNX_Shading:shading_slat"}
		Switch           shading_manual         "Shading manual"
		Rollershutter    shading_all_ctr        "Shading all ctr [%s %%]"           <rollershutter>     {channel="knx:device:bridge:KNX_Shading:shading_group_all_ctr"}
		Switch           shading_hand_manual    "Shading in Hand / Manual state"                        {channel="knx:device:bridge:KNX_Shading:shading_hand_manual_ctr"}


		# Rule init:
		habapp_rules.actors.shading.Raffstore(
			"shading_position",
			"shading_slat",
			"shading_manual",
			habapp_rules.actors.config.shading.CONFIG_DEFAULT,
			["shading_position_ctr", "shading_all_ctr"],
			[],
			"I99_99_WindAlarm",
			"I99_99_SunProtection",
			"I99_99_SunProtection_Slat",
			"I99_99_Sleeping_State",
			"I99_99_Night",
			"I99_99_Door",
			"I99_99_Summer"
			"shading_hand_manual"
		)
		"""

	# pylint: disable=too-many-locals
	def __init__(self,
	             name_shading_position: str,
	             name_slat: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.shading.ShadingConfig,
	             shading_position_control_names: list[str] | None = None,
	             shading_position_group_names: list[str] | None = None,
	             name_wind_alarm: str | None = None,
	             name_sun_protection: str | None = None,
	             name_sun_protection_slat: str | None = None,
	             name_sleeping_state: str | None = None,
	             name_night: str | None = None,
	             name_door: str | None = None,
	             name_summer: str | None = None,
	             name_hand_manual_is_active_feedback: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of Raffstore object.

		:param name_shading_position: name of OpenHAB shading item (RollershutterItem)
		:param name_slat: name of OpenHAB slat item (DimmerItem)
		:param name_manual: name of OpenHAB switch item to disable all automatic functions
		:param config: configuration of the shading object
		:param shading_position_control_names: [optional] list of control items.
		:param shading_position_group_names: [optional]  list of group items where the item is a part of. Group item type must match with type of item_name
		:param name_wind_alarm: [optional] name of OpenHAB switch item which is 'ON' when wind-alarm is active
		:param name_sun_protection: [optional] name of OpenHAB switch item which is 'ON' when sun protection is active
		:param name_sun_protection_slat:
		:param name_sleeping_state: [optional] name of OpenHAB sleeping state item (StringItem)
		:param name_night: [optional] name of OpenHAB switch item which is 'ON' when it is dark and 'OFF' when it is bright
		:param name_door: [optional] name of OpenHAB door item (ContactItem)
		:param name_summer: [optional] name of OpenHAB switch item which is 'ON' during summer and 'OFF' during winter
		:param name_hand_manual_is_active_feedback: [optional] name of OpenHAB switch item which is 'ON' if state is manual or hand
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: [optional] label of OpenHAB item for storing the current state (StringItem)
		"""
		_ShadingBase.__init__(
			self,
			name_shading_position,
			name_manual,
			config,
			shading_position_control_names,
			shading_position_group_names,
			name_wind_alarm, name_sun_protection,
			name_sleeping_state,
			name_night, name_door,
			name_summer,
			name_hand_manual_is_active_feedback,
			name_state,
			state_label
		)

		self._state_observer_slat = habapp_rules.actors.state_observer.StateObserverDimmer(name_slat, self._cb_hand, self._cb_hand, self._cb_hand)

		# init items
		self._item_slat = HABApp.openhab.items.dimmer_item.DimmerItem.get_item(name_slat)
		self._item_sun_protection_slat = HABApp.openhab.items.dimmer_item.DimmerItem.get_item(name_sun_protection_slat) if name_sun_protection_slat else None
		self.__verify_items()

		# callbacks
		if self._item_sun_protection_slat is not None:
			self._item_sun_protection_slat.listen_event(self._cb_slat_target, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._instance_logger.debug(self.get_initial_log_message())

	def __verify_items(self) -> None:
		"""Check if given items are valid

		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if given items are not valid
		"""
		# check type of rollershutter item
		if not isinstance(self._item_shading_position, HABApp.openhab.items.rollershutter_item.RollershutterItem):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"The shading position item must be of type RollershutterItem. Given: {type(self._item_shading_position)}")

		# check if the correct items are given for sun protection mode
		if (self._item_sun_protection is None) != (self._item_sun_protection_slat is None):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("Ether sun_protection item AND sun_protection_slat item must be given or None of them.")

	def _get_target_position(self) -> habapp_rules.actors.config.shading.ShadingPosition | None:
		"""Get target position for shading object(s).

		:return: target shading position
		"""
		target_position = super()._get_target_position()

		if self.state == "Auto_SunProtection" and target_position is not None:
			target_position.slat = self._item_sun_protection_slat.value

		return target_position

	def _set_shading_state(self) -> None:
		"""Set shading state"""
		if self._previous_state is None:
			# don't change value if called during init (_previous_state == None)
			return

		target_position = self._get_target_position()

		if target_position is None:
			return

		if (position := target_position.position) is not None:
			self._state_observer_pos.send_command(position)

		if (slat := target_position.slat) is not None:
			self._state_observer_slat.send_command(slat)

		if any(pos is not None for pos in (position, slat)):
			self._instance_logger.debug(f"set position {target_position}")

	def _set_position_before(self) -> None:
		"""Set / save position before manual state is entered. This is used to restore the previous position"""
		self._position_before = habapp_rules.actors.config.shading.ShadingPosition(self._item_shading_position.value, self._item_slat.value)

	def _cb_slat_target(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if the target slat value changed.

		:param event: original trigger event
		"""
		if self.state == "Auto_SunProtection":
			self._state_observer_slat.send_command(event.value)


class ResetAllManualHand(HABApp.Rule):
	"""Clear the state hand / manual state of all shading

	# Items:
	Switch           clear_hand_manual         "Clear Hand / Manual state of all shading objects"

	# Rule init:
	habapp_rules.actors.shading.ResetAllManualHand("clear_hand_manual")
	"""

	def __init__(self, name_reset_manual_hand: str) -> None:
		"""Init of reset class.

		:param name_reset_manual_hand: name of OpenHAB reset item (SwitchItem)
		"""
		HABApp.Rule.__init__(self)
		self._item_reset = HABApp.openhab.items.SwitchItem.get_item(name_reset_manual_hand)
		self._item_reset.listen_event(self._cb_reset_all, HABApp.openhab.events.ItemCommandEventFilter())

	def __get_shading_objects(self) -> list[type(_ShadingBase)]:
		"""Get all shading objects.

		:return: list of shading objects
		"""
		return [rule for rule in self.get_rule(None) if issubclass(rule.__class__, _ShadingBase)]

	def _cb_reset_all(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback which is called if reset is requested

		:param event: trigger event
		"""
		if event.value == "OFF":
			return

		for shading_object in self.__get_shading_objects():
			state = shading_object.state
			manual_item: HABApp.openhab.items.SwitchItem = shading_object._item_manual  # pylint: disable=protected-access

			if state == "Manual":
				manual_item.oh_send_command("OFF")

			elif state == "Hand":
				manual_item.oh_send_command("ON")
				manual_item.oh_send_command("OFF")

		self._item_reset.oh_send_command("OFF")


class SlatValueSun(HABApp.Rule):
	"""Rules class to get slat value depending on sun elevation.

		# Items:
		Number    elevation             "Sun elevation [%s]"    <sun>     {channel="astro...}
		Number    sun_protection_slat   "Slat value [%s %%]"    <slat>

		# Rule init:
		habapp_rules.actors.shading.SlatValueSun(
			"elevation",
			"sun_protection_slat",
			habapp_rules.actors.config.shading.CONFIG_DEFAULT_ELEVATION_SLAT_WINTER,
			"I99_99_Summer",
			habapp_rules.actors.config.shading.CONFIG_DEFAULT_ELEVATION_SLAT_SUMMER,
		)
		"""

	_item_slat_value: HABApp.openhab.items.dimmer_item.DimmerItem | HABApp.openhab.items.number_item.NumberItem

	def __init__(self,
	             name_sun_elevation: str,
	             name_slat_value: str,
	             elevation_slat_characteristic: list[(float | int, float | int)],
	             name_summer: str | None = None,
	             elevation_slat_characteristic_summer: list[(float | int, float | int)] | None = None):
		"""Init SlatValueSun

		:param name_sun_elevation: name of OpenHAB sun elevation item (NumberItem)
		:param name_slat_value: name of OpenHAB target slat item (NumberItem | DimmerItem)
		:param elevation_slat_characteristic: List of tuple-mappings from elevation to slat value
		:param name_summer: name of OpenHAB summer item (SwitchItem)
		:param elevation_slat_characteristic_summer: List of tuple-mappings from elevation to slat value, which is used if summer is active
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if configuration is not valid
		"""
		if (name_summer is None) != (elevation_slat_characteristic_summer is None):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("Ether both 'name_summer' and 'elevation_slat_characteristic_summer' must be None or a value.")

		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_slat_value)

		# init items
		self._item_sun_elevation = HABApp.openhab.items.number_item.NumberItem.get_item(name_sun_elevation)
		self._item_slat_value = HABApp.openhab.items.OpenhabItem.get_item(name_slat_value)
		self._item_summer = HABApp.openhab.items.switch_item.SwitchItem.get_item(name_summer) if name_summer else None

		if not isinstance(self._item_slat_value, (HABApp.openhab.items.dimmer_item.DimmerItem, HABApp.openhab.items.number_item.NumberItem)):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("Item slat_value must be of type DimmerItem or NumberItem!")

		# slat characteristics
		self.__slat_characteristic_default = self.__check_and_sort_characteristic(elevation_slat_characteristic)
		self.__slat_characteristic_summer = self.__check_and_sort_characteristic(elevation_slat_characteristic_summer) if elevation_slat_characteristic_summer else None
		self._slat_characteristic_active = self.__slat_characteristic_summer if bool(self._item_summer) else self.__slat_characteristic_default

		# callbacks
		self._item_sun_elevation.listen_event(self._cb_elevation, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_summer is not None:
			self._item_summer.listen_event(self._cb_summer_winter, HABApp.openhab.events.ItemStateChangedEventFilter())
		self.run.soon(self.__send_slat_value)

		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with name '{self.rule_name}' was successful.")

	@staticmethod
	def __check_and_sort_characteristic(characteristic: list[(float | int, float | int)]) -> list[(float, float)]:
		"""Check and sort characteristic

		:param characteristic: characteristic for slats. First value must be elevation, second the slat value
		:return: sorted characteristic
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if characteristic is not valid
		"""

		if not isinstance(characteristic, list) or not all(isinstance(itm, tuple) and len(itm) == 2 for itm in characteristic):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("Characteristic must be a list of value pairs as tuple")

		if len(set(value_pair[0] for value_pair in characteristic)) != len(characteristic):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("Elevation values must be unique!")

		return sorted(characteristic)

	def __get_slat_value(self, elevation: float) -> float:
		"""Get slat value for given elevation.

		:param elevation: elevation of the sun
		:return: slat value
		"""
		if elevation >= self._slat_characteristic_active[-1][0]:
			return self._slat_characteristic_active[-1][1]
		if elevation < self._slat_characteristic_active[0][0]:
			return self._slat_characteristic_active[0][1]

		# no cover because of loop does not finish, but is handled with the two if statements above
		return next(config for idx, config in enumerate(self._slat_characteristic_active) if config[0] <= elevation < self._slat_characteristic_active[idx + 1][0])[1]  # pragma: no cover

	def __send_slat_value(self) -> None:
		"""Send slat value to OpenHAB item."""
		slat_value = self.__get_slat_value(self._item_sun_elevation.value)

		if self._item_slat_value.value != slat_value:
			self._item_slat_value.oh_send_command(slat_value)

	def _cb_elevation(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is called if sun elevation changed

		:param event: elevation event
		"""
		self.__send_slat_value()

	def _cb_summer_winter(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		"""Callback which is called if summer / winter changed

		:param event: summer / winter event
		"""
		self._slat_characteristic_active = self.__slat_characteristic_summer if event.value == "ON" else self.__slat_characteristic_default
		self.__send_slat_value()
