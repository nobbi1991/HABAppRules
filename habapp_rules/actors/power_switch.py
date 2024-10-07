import logging

import HABApp

import habapp_rules.actors.config.power_switch
import habapp_rules.actors.state_observer
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule

# todo: config, off at night / absence / max time
# todo: switch with power measurement
# todo: search for light and change to power_switch
LOGGER = logging.getLogger(__name__)


class Switch(habapp_rules.core.state_machine_rule.StateMachineRule):
	"""Base class for switch."""
	states = [
		{"name": "Manual"},
		{"name": "Hand", "timeout": 20 * 3600, "on_timeout": "_auto_hand_timeout"},
		{"name": "Auto", "initial": "init", "children": [
			{"name": "Init"},
			{"name": "On", "timeout": 10, "on_timeout": "auto_on_timeout"},
			{"name": "Off"},
			{"name": "RestoreState"}  # todo implement
		]}
	]

	trans = [
		{"trigger": "manual_on", "source": "Auto", "dest": "Manual"}, # todo also hand
		{"trigger": "manual_off", "source": "Manual", "dest": "Auto"},
		{"trigger": "hand", "source": "Auto", "dest": "Hand"},

		{"trigger": "Auto_On_Timeout", "source": "Auto_On", "dest": "Auto_Off"},
		{"trigger": "presence_sleeping_target_on", "source": "auto_off", "dest": "auto_on"},
		{"trigger": "presence_sleeping_target_off", "source": "auto_on", "dest": "auto_off"},
	]

	def __init__(self,
	             name_switch: str,
	             manual_name: str,
	             config: habapp_rules.actors.config.power_switch.PowerSwitchConfig,
	             presence_state_name: str | None = None,
	             sleeping_state_name: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of switch object.

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
			name_state = f"H_{name_switch}_state"
		habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, name_state, state_label)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_switch)

		# init items
		self._item_switch: HABApp.openhab.items.switch_item.SwitchItem.get_item(name_switch)
		self._item_manual = HABApp.openhab.items.switch_item.SwitchItem.get_item(manual_name)
		self._item_presence_state = HABApp.openhab.items.string_item.StringItem.get_item(presence_state_name) if presence_state_name else None
		self._item_sleeping_state = HABApp.openhab.items.string_item.StringItem.get_item(sleeping_state_name) if sleeping_state_name else None

		# init state machine
		self._previous_state = None
		self._restore_state = None
		self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")

		self._brightness_before = -1  # todo change
		self._timeout_on = 0
		self._set_timeouts()
		self._set_initial_state()

		# callbacks
		self._item_manual.listen_event(self._cb_manu, HABApp.openhab.events.ItemStateUpdatedEventFilter())
		if self._item_sleeping_state is not None:
			self._item_sleeping_state.listen_event(self._cb_sleeping, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_presence_state.listen_event(self._cb_presence, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_day.listen_event(self._cb_day, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._update_openhab_state()

		habapp_rules.actors.state_observer.StateObserverSwitch(name_switch, self._cb_hand_on, self._cb_hand_off)

		self._instance_logger.debug(super().get_initial_log_message())
