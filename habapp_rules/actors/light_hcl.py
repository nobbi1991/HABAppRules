"""Light HCL rules."""
import abc
import datetime
import logging

import HABApp

import habapp_rules.actors.config.light_hcl
import habapp_rules.actors.state_observer
import habapp_rules.core.exceptions
import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.core.type_of_day
import habapp_rules.system

LOGGER = logging.getLogger(__name__)


# pylint: disable=no-member
class _HclBase(habapp_rules.core.state_machine_rule.StateMachineRule):
	"""Base class for HCL rules."""

	states = [
		{"name": "Manual"},
		{"name": "Hand", "timeout": 99, "on_timeout": "hand_timeout"},
		{"name": "Auto", "initial": "Init", "children": [
			{"name": "Init"},
			{"name": "HCL"},
			{"name": "Sleep", "initial": "Active", "children": [
				{"name": "Active"},
				{"name": "Post", "timeout": 1, "on_timeout": "post_sleep_timeout"}
			]},
			{"name": "Focus"}
		]}
	]

	trans = [
		{"trigger": "manual_on", "source": ["Auto", "Hand"], "dest": "Manual"},
		{"trigger": "manual_off", "source": "Manual", "dest": "Auto"},

		{"trigger": "hand_on", "source": "Auto", "dest": "Hand"},
		{"trigger": "hand_timeout", "source": "Hand", "dest": "Auto"},

		{"trigger": "sleep_start", "source": ["Auto_HCL", "Auto_Focus"], "dest": "Auto_Sleep"},
		{"trigger": "sleep_end", "source": "Auto_Sleep_Active", "dest": "Auto_Sleep_Post"},
		{"trigger": "post_sleep_timeout", "source": "Auto_Sleep_Post", "dest": "Auto_HCL"},

		{"trigger": "focus_start", "source": ["Auto_HCL", "Auto_Sleep"], "dest": "Auto_Focus"},
		{"trigger": "focus_end", "source": "Auto_Focus", "dest": "Auto_HCL"},
	]

	def __init__(self,
	             name_color: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.light_hcl.LightHclConfig,
	             name_sleep_state: str | None = None,
	             name_focus: str | None = None,
	             name_switch_on: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init base class.

		:param name_color: Name of openHAB color item (NumberItem)
    	:param name_manual: name of OpenHAB switch item to disable all automatic functions (SwitchItem)
		:param config: config for HCL rule
		:param name_sleep_state: [optional] name of OpenHAB sleeping state item (StringItem)
		:param name_focus: [optional] name of OpenHAB focus state item (SwitchItem)
		:param name_switch_on: name of OpenHAB switch item, which additionally triggers a color update if switched on. This can be used to also trigger an update if the power supply or a single light switched on
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		"""
		self._config = config

		if not name_state:
			name_state = f"H_{name_color}_state"

		habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, name_state, state_label)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_color)

		# get items
		self._item_color = HABApp.openhab.items.NumberItem.get_item(name_color)
		self._item_manual = HABApp.openhab.items.SwitchItem.get_item(name_manual)
		self._item_sleep = HABApp.openhab.items.StringItem.get_item(name_sleep_state) if name_sleep_state else None
		self._item_focus = HABApp.openhab.items.SwitchItem.get_item(name_focus) if name_focus else None
		self._item_switch_on = HABApp.openhab.items.SwitchItem.get_item(name_switch_on) if name_switch_on else None

		self._validate_config()
		self._state_observer = habapp_rules.actors.state_observer.StateObserverNumber(name_color, self._cb_hand, value_tolerance=10)

		# init state machine
		self._previous_state = None
		self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")
		self._set_initial_state()

		self._set_timeouts()

		# set callbacks
		self._item_manual.listen_event(self._cb_manual, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_sleep is not None:
			self._item_sleep.listen_event(self._cb_sleep, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_focus is not None:
			self._item_focus.listen_event(self._cb_focus, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_switch_on is not None:
			self._item_switch_on.listen_event(self._cb_switch_on, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _validate_config(self) -> None:
		"""Validate configuration.

		:raises habapp_rules.common.exceptions.HabAppRulesConfigurationException: if config is not valid.
		"""

		if (self._item_sleep is None) != (self._config.sleep_color is None):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("Ether item_sleep and sleep_color must be given or none of them!")

		if (self._item_focus is None) != (self._config.focus_color is None):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("Ether item_focus and focus_color must be given or none of them!")

	def _set_timeouts(self) -> None:
		"""Set timeouts."""
		self.state_machine.get_state("Auto_Sleep_Post").timeout = self._config.post_sleep_timeout if self._config.post_sleep_timeout else 1
		self.state_machine.get_state("Hand").timeout = self._config.hand_timeout if self._config.hand_timeout else 0

	def _get_initial_state(self, default_value: str = "") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		if self._item_manual.is_on():
			return "Manual"
		if self._item_sleep is not None and self._item_sleep.value in (habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value):
			return "Auto_Sleep"
		if self._item_focus is not None and self._item_focus.is_on():
			return "Auto_Focus"
		return "Auto_HCL"

	def _update_openhab_state(self) -> None:
		"""Update OpenHAB state item and other states.

		This should method should be set to "after_state_change" of the state machine.
		"""
		if self.state != self._previous_state:
			super()._update_openhab_state()
			self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

			self._set_light_color()
			self._previous_state = self.state

	def _set_light_color(self):
		"""Set light color."""
		target_color = None

		if self.state == "Auto_HCL":
			target_color = self._get_hcl_color()
		elif self.state == "Auto_Focus":
			target_color = self._config.focus_color
		elif self.state == "Auto_Sleep_Active":
			target_color = self._config.sleep_color

		if target_color is not None:
			self._state_observer.send_command(target_color)

	def on_enter_Auto_Init(self) -> None:  # pylint: disable=invalid-name
		"""Is called on entering of init state"""
		self._set_initial_state()

	@abc.abstractmethod
	def _get_hcl_color(self) -> float | None:
		"""Get HCL color.

		:return: HCL light color
		"""

	@staticmethod
	def _get_interpolated_value(config_start: tuple[float, float], config_end: tuple[float, float], value: float) -> float:
		"""Get interpolated value

		:param config_start: start config
		:param config_end: end config
		:param value: input value which is the input for the interpolation
		:return: interpolated value
		"""
		fit_m = (config_end[1] - config_start[1]) / (config_end[0] - config_start[0])
		fit_t = config_end[1] - fit_m * config_end[0]

		return fit_m * value + fit_t

	def _cb_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the manual switch has a state change event.

		:param event: trigger event
		"""
		if event.value == "ON":
			self.manual_on()
		else:
			self.manual_off()

	def _cb_hand(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is triggered by the state observer if a manual change was detected.

		:param event: original trigger event
		"""
		self._instance_logger.debug("Hand detected")
		self.hand_on()

	def _cb_focus(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the focus switch has a state change event.

		:param event: trigger event
		"""
		if event.value == "ON":
			self.focus_start()
		else:
			self.focus_end()

	def _cb_sleep(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the sleep state has a state change event.

		:param event: trigger event
		"""
		if event.value == habapp_rules.system.SleepState.PRE_SLEEPING.value:
			self.sleep_start()
			if self._item_focus and self._item_focus.is_on():
				self._item_focus.oh_send_command("OFF")
		elif event.value == habapp_rules.system.SleepState.AWAKE.value:
			self.sleep_end()

	def _cb_switch_on(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the switch_on_item has a state change event.

		:param event: trigger event
		"""
		if event.value == "ON" and self.state == "Auto_HCL":
			if (target_color := self._get_hcl_color()) is not None:
				self.run.at(1, self._state_observer.send_command, target_color)


class HclElevation(_HclBase):
	"""Sun elevation based HCL.

		# Items:
		Number    Elevation                     "Elevation [%s]"                {channel="astro:sun:home:position#elevation"}
		Number    HCL_Color_Elevation           "HCL Color Elevation"
		Switch    HCL_Color_Elevation_manual    "HCL Color Elevation manual"

		# Rule init:
		habapp_rules.actors.light_hcl.HclElevation(
			"Elevation",
			"HCL_Color_Elevation",
			"HCL_Color_Elevation_manual",
			config=habapp_rules.actors.config.light_hcl.EXAMPLE_CONFIG_ELEVATION,
		)
	"""

	def __init__(self,
	             name_elevation: str,
	             name_color: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.light_hcl.LightHclConfig,
	             name_sleep_state: str | None = None,
	             name_focus: str | None = None,
	             name_switch_on: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None
	             ):
		"""Init sun elevation based HCL rule.

		:param name_elevation: Name of sun elevation openHAB item (NumberItem)
		:param name_color: Name of openHAB color item (NumberItem)
    	:param name_manual: name of OpenHAB switch item to disable all automatic functions (SwitchItem)
		:param config: config for HCL rule
		:param name_sleep_state: [optional] name of OpenHAB sleeping state item (StringItem)
		:param name_focus: [optional] name of OpenHAB focus state item (SwitchItem)
		:param name_switch_on: name of OpenHAB switch item, which additionally triggers a color update if switched on. This can be used to also trigger an update if the power supply or a single light switched on
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		"""
		self._item_elevation = HABApp.openhab.items.NumberItem.get_item(name_elevation)

		_HclBase.__init__(self, name_color, name_manual, config, name_sleep_state, name_focus, name_switch_on, name_state, state_label)

		self._item_elevation.listen_event(self._cb_elevation, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._cb_elevation(None)

	def _get_hcl_color(self) -> float | None:
		"""Get HCL color depending on elevation

		:return: HCL light color
		"""
		elevation = self._item_elevation.value

		if elevation is None:
			return None

		return_value = 0
		if elevation <= self._config.color_config[0][0]:
			return_value = self._config.color_config[0][1]

		elif elevation >= self._config.color_config[-1][0]:
			return_value = self._config.color_config[-1][1]

		else:
			for idx, config_itm in enumerate(self._config.color_config):  # pragma: no cover
				if config_itm[0] <= elevation <= self._config.color_config[idx + 1][0]:
					return_value = self._get_interpolated_value(config_itm, self._config.color_config[idx + 1], elevation)
					break

		return return_value

	def _cb_elevation(self, _: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
		"""Callback which is called if elevation changed"""
		if self.state == "Auto_HCL" and self._item_elevation.value is not None:
			self._state_observer.send_command(self._get_hcl_color())


class HclTime(_HclBase):
	"""Time based HCL.
		# Items:
		Number    HCL_Color_Time           "HCL Color Time"
		Switch    HCL_Color_Time_manual    "HCL Color Time manual"

		# Rule init:
		habapp_rules.actors.light_hcl.HclTime(
			"HCL_Color_Time",
			"HCL_Color_Time_manual",
			config=habapp_rules.actors.config.light_hcl.EXAMPLE_CONFIG_ELEVATION,
		)
	"""

	def __init__(self,
	             name_color: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.light_hcl.LightHclConfig,
	             name_sleep_state: str | None = None,
	             name_focus: str | None = None,
	             name_switch_on: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None
	             ) -> None:
		"""Init time based HCL rule.

		:param name_color: Name of openHAB color item (NumberItem)
    	:param name_manual: name of OpenHAB switch item to disable all automatic functions (SwitchItem)
		:param config: config for HCL rule
		:param name_sleep_state: [optional] name of OpenHAB sleeping state item (StringItem)
		:param name_focus: [optional] name of OpenHAB focus state item (SwitchItem)
		:param name_switch_on: name of OpenHAB switch item, which additionally triggers a color update if switched on. This can be used to also trigger an update if the power supply or a single light switched on
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		"""
		_HclBase.__init__(self, name_color, name_manual, config, name_sleep_state, name_focus, name_switch_on, name_state, state_label)
		self.run.every(None, 300, self._update_color)  # every 5 minutes

	def _one_hour_later(self, current_time: datetime.datetime) -> bool:
		"""Check if today the color values will be shifted one hour later in the evening

		:param current_time: current time
		:return: True if next day is a weekend / holiday day
		"""
		if not self._config.shift_weekend_holiday:
			return False

		if current_time.hour > 12 and (habapp_rules.core.type_of_day.is_holiday(1) or habapp_rules.core.type_of_day.is_weekend(1)):
			return True
		if current_time.hour <= 4 and (habapp_rules.core.type_of_day.is_holiday() or habapp_rules.core.type_of_day.is_weekend()):
			return True
		return False

	def _get_hcl_color(self) -> float | None:
		"""Get HCL color depending on time

		:return: HCL light color
		"""
		current_time = datetime.datetime.now()

		if self._one_hour_later(current_time):
			current_time -= datetime.timedelta(hours=1)

		if current_time.hour < self._config.color_config[0][0]:
			start_config = (self._config.color_config[-1][0] - 24, self._config.color_config[-1][1])
			end_config = self._config.color_config[0]

		elif current_time.hour >= self._config.color_config[-1][0]:
			start_config = self._config.color_config[-1]
			end_config = (self._config.color_config[0][0] + 24, self._config.color_config[0][1])

		else:
			for idx, config_itm in enumerate(self._config.color_config):  # pragma: no cover
				if config_itm[0] <= current_time.hour < self._config.color_config[idx + 1][0]:
					start_config = config_itm
					end_config = self._config.color_config[idx + 1]
					break

		return self._get_interpolated_value(start_config, end_config, current_time.hour + current_time.minute / 60)

	def _update_color(self) -> None:
		"""Callback which is called every 5 minutes"""
		if self.state == "Auto_HCL":
			self._state_observer.send_command(self._get_hcl_color())
