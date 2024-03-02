"""Ventilation rules."""
import abc
import copy
import datetime
import logging

import HABApp

import habapp_rules.actors.config.ventilation
import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system

LOGGER = logging.getLogger(__name__)


# pylint: disable=no-member
class _VentilationBase(habapp_rules.core.state_machine_rule.StateMachineRule):
	"""Class for ventilation objects."""

	states = [
		{"name": "Manual"},
		{"name": "Auto", "initial": "Init", "children": [
			{"name": "Init"},
			{"name": "Normal"},
			{"name": "PowerHand", "timeout": 3600, "on_timeout": "_hand_off"},
			{"name": "PowerExternal"},
			{"name": "LongAbsence", "initial": "Off", "children": [
				{"name": "On", "timeout": 3600, "on_timeout": "_long_absence_power_off"},
				{"name": "Off"}
			]},
		]}
	]

	trans = [
		# manual
		{"trigger": "_manual_on", "source": ["Auto"], "dest": "Manual"},
		{"trigger": "_manual_off", "source": "Manual", "dest": "Auto"},

		# PowerHand
		{"trigger": "_hand_on", "source": ["Auto_Normal", "Auto_PowerExternal", "Auto_LongAbsence"], "dest": "Auto_PowerHand"},
		{"trigger": "_hand_off", "source": "Auto_PowerHand", "dest": "Auto_PowerExternal", "conditions": "_external_active_and_configured"},
		{"trigger": "_hand_off", "source": "Auto_PowerHand", "dest": "Auto_Normal", "unless": "_external_active_and_configured"},

		# PowerExternal
		{"trigger": "_external_on", "source": "Auto_Normal", "dest": "Auto_PowerExternal"},
		{"trigger": "_external_off", "source": "Auto_PowerExternal", "dest": "Auto_Normal"},

		# long absence
		{"trigger": "_long_absence_on", "source": ["Auto_Normal", "Auto_PowerExternal"], "dest": "Auto_LongAbsence"},
		{"trigger": "_long_absence_power_on", "source": "Auto_LongAbsence_Off", "dest": "Auto_LongAbsence_On"},
		{"trigger": "_long_absence_power_off", "source": "Auto_LongAbsence_On", "dest": "Auto_LongAbsence_Off"},
		{"trigger": "_long_absence_off", "source": "Auto_LongAbsence", "dest": "Auto_Normal"},
	]

	# pylint: disable=too-many-arguments
	def __init__(self,
	             name_manual: str,
	             config: habapp_rules.actors.config.ventilation.VentilationConfig,
	             name_hand_request: str | None = None,
	             name_external_request: str | None = None,
	             name_presence_state: str | None = None,
	             name_feedback_on: str | None = None,
	             name_feedback_power: str | None = None,
	             name_display_text: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of ventilation base.

		:param name_manual: name of OpenHAB switch item to disable all automatic functions  (SwitchItem)
		:param config: configuration of the ventilation
		:param name_hand_request: name of OpenHAB switch item to enter the hand state (SwitchItem)
		:param name_external_request: name of OpenHAB switch item to enter the external state (e.g. used for dryer request) (SwitchItem)
		:param name_presence_state: name of OpenHAB presence state item (StringItem)
		:param name_feedback_on: name of OpenHAB item which shows that ventilation is on (SwitchItem)
		:param name_feedback_power: name of OpenHAB item which shows that ventilation is in power mode (SwitchItem)
		:param name_display_text: name of OpenHAB item which can be used to set the display text (e.g. for user interface) (StringItem)
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		"""

		self._config = config
		self._ventilation_level: int | None = None

		habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, name_state, state_label)

		# init items
		self._item_manual = HABApp.openhab.items.SwitchItem.get_item(name_manual)
		self._item_hand_request = HABApp.openhab.items.SwitchItem.get_item(name_hand_request) if name_hand_request else None
		self._item_external_request = HABApp.openhab.items.SwitchItem.get_item(name_external_request) if name_external_request else None
		self._item_presence_state = HABApp.openhab.items.StringItem.get_item(name_presence_state) if name_presence_state else None
		self._item_feedback_on = HABApp.openhab.items.SwitchItem.get_item(name_feedback_on) if name_feedback_on else None
		self._item_feedback_power = HABApp.openhab.items.SwitchItem.get_item(name_feedback_power) if name_feedback_power else None
		self._item_display_text = HABApp.openhab.items.StringItem.get_item(name_display_text) if name_display_text else None

		# init state machine
		self._previous_state = None
		self._state_change_time = datetime.datetime.now()
		self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")
		self._set_initial_state()

		self._apply_config()

		# callbacks
		self._item_manual.listen_event(self._cb_manual, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_hand_request is not None:
			self._item_hand_request.listen_event(self._cb_power_hand_request, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_external_request is not None:
			self._item_external_request.listen_event(self._cb_external_request, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_presence_state is not None:
			self._item_presence_state.listen_event(self._cb_presence_state, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._update_openhab_state()

	def _get_initial_state(self, default_value: str = "initial") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		if self._item_manual.is_on():
			return "Manual"
		if self._item_hand_request is not None and self._item_hand_request.is_on():
			return "Auto_PowerHand"
		if self._item_presence_state is not None and self._item_presence_state.value == habapp_rules.system.PresenceState.LONG_ABSENCE.value:
			return "Auto_LongAbsence"
		if self._item_external_request is not None and self._item_external_request.is_on():
			return "Auto_PowerExternal"
		return "Auto_Normal"

	def _apply_config(self) -> None:
		"""Apply values from config."""
		self.state_machine.get_state("Auto_PowerHand").timeout = self._config.state_hand.timeout
		self.state_machine.get_state("Auto_LongAbsence_On").timeout = self._config.state_long_absence.duration

	def _update_openhab_state(self) -> None:
		"""Update OpenHAB state item and other states.

		This method should be set to "after_state_change" of the state machine.
		"""
		if self.state != self._previous_state:
			super()._update_openhab_state()
			self._state_change_time = datetime.datetime.now()
			self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")

			self._set_level()
			self._set_feedback_states()
			self._previous_state = self.state

	def _set_level(self) -> None:
		"""Set ventilation level"""
		if self.state == "Manual":
			return

		if self.state == "Auto_PowerHand":
			self._ventilation_level = self._config.state_hand.level
		elif self.state == "Auto_Normal":
			self._ventilation_level = self._config.state_normal.level
		elif self.state == "Auto_PowerExternal":
			self._ventilation_level = self._config.state_external.level
		elif self.state == "Auto_LongAbsence_On":
			self._ventilation_level = self._config.state_long_absence.level
		elif self.state == "Auto_LongAbsence_Off":
			self._ventilation_level = 0
		else:
			return

		self._set_level_to_ventilation_items()

	@abc.abstractmethod
	def _set_level_to_ventilation_items(self) -> None:
		"""Set ventilation to output item(s)."""

	def _get_display_text(self) -> str | None:
		"""Get Text for display.

		:return: text for display or None if not defined for this state
		"""
		if self.state == "Manual":
			return "Manual"
		if self.state == "Auto_Normal":
			return self._config.state_normal.display_text
		if self.state == "Auto_PowerExternal":
			return self._config.state_external.display_text
		if self.state == "Auto_LongAbsence_On":
			return f"{self._config.state_long_absence.display_text} ON"
		if self.state == "Auto_LongAbsence_Off":
			return f"{self._config.state_long_absence.display_text} OFF"

		return None

	def _set_feedback_states(self) -> None:
		"""Set feedback sates to the OpenHAB items."""
		if self._item_hand_request is not None and self._previous_state == "Auto_PowerHand":
			habapp_rules.core.helper.send_if_different(self._item_hand_request, "OFF")

		if self._item_feedback_on is not None:
			habapp_rules.core.helper.send_if_different(self._item_feedback_on, "ON" if self._ventilation_level else "OFF")

		if self._item_feedback_power is not None:
			target_value = "ON" if self._ventilation_level is not None and self._ventilation_level >= 2 else "OFF"
			habapp_rules.core.helper.send_if_different(self._item_feedback_power, target_value)

		if self._item_display_text is not None:
			if self.state == "Auto_PowerHand":
				self.__set_hand_display_text()
				return

			if (display_text := self._get_display_text()) is not None:
				habapp_rules.core.helper.send_if_different(self._item_display_text, display_text)

	def __set_hand_display_text(self) -> None:
		"""Callback to set display text."""
		if self.state != "Auto_PowerHand":
			# state changed and is not PowerHand anymore
			return

		# get the remaining minutes and set display text
		remaining_minutes = round((self._config.state_hand.timeout - (datetime.datetime.now() - self._state_change_time).seconds) / 60)
		remaining_minutes = remaining_minutes if remaining_minutes >= 0 else 0
		habapp_rules.core.helper.send_if_different(self._item_display_text, f"{self._config.state_hand.display_text} {remaining_minutes}min")

		# re-trigger this method in 1 minute
		self.run.at(60, self.__set_hand_display_text)

	def on_enter_Auto_Init(self) -> None:  # pylint: disable=invalid-name
		"""Is called on entering of Auto_Init state"""
		self._set_initial_state()

	def on_enter_Auto_LongAbsence_Off(self):  # pylint: disable=invalid-name
		"""Is called on entering of Auto_LongAbsence_Off state."""
		self.run.at(self._config.state_long_absence.start_time, self._long_absence_power_on)  # todo test in real

	def _external_active_and_configured(self) -> bool:
		"""Check if external request is active and configured.

		:return: True if external request is active and configured
		"""
		return self._item_external_request is not None and self._item_external_request.is_on()

	def _cb_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if manual mode changed.

		:param event: original trigger event
		"""
		if event.value == "ON":
			self._manual_on()
		else:
			self._manual_off()

	def _cb_power_hand_request(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if power_hand_request changed.

		:param event: original trigger event
		"""
		if event.value == "ON":
			self._hand_on()
		else:
			self._hand_off()

	def _cb_external_request(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if external request changed.

		:param event: original trigger event
		"""
		if event.value == "ON":
			self._external_on()
		else:
			self._external_off()

	def _cb_presence_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if presence_state changed.

		:param event: original trigger event
		"""
		if event.value == habapp_rules.system.PresenceState.LONG_ABSENCE.value:
			self._long_absence_on()
		else:
			self._long_absence_off()


class Ventilation(_VentilationBase):
	""""""  # todo add text + example

	# pylint: disable=too-many-arguments
	def __init__(self,
	             name_ventilation_level: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.ventilation.VentilationConfig,
	             name_hand_request: str | None = None,
	             name_external_request: str | None = None,
	             name_presence_state: str | None = None,
	             name_feedback_on: str | None = None,
	             name_feedback_power: str | None = None,
	             name_display_text: str | None = None,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of ventilation object.

		:param name_ventilation_level: name of OpenHAB number item to set the ventilation level (NumberItem
		:param name_manual: name of OpenHAB switch item to disable all automatic functions  (SwitchItem)
		:param config: configuration of the ventilation
		:param name_hand_request: name of OpenHAB switch item to enter the hand state (SwitchItem)
		:param name_external_request: name of OpenHAB switch item to enter the external state (e.g. used for dryer request) (SwitchItem)
		:param name_presence_state: name of OpenHAB presence state item (StringItem)
		:param name_feedback_on: name of OpenHAB item which shows that ventilation is on (SwitchItem)
		:param name_feedback_power: name of OpenHAB item which shows that ventilation is in power mode (SwitchItem)
		:param name_display_text: name of OpenHAB item which can be used to set the display text (e.g. for user interface) (StringItem)
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		"""
		if not name_state:
			name_state = f"H_{name_ventilation_level}_state"
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_ventilation_level)

		self._item_ventilation_level = HABApp.openhab.items.NumberItem.get_item(name_ventilation_level)

		_VentilationBase.__init__(
			self,
			name_manual,
			config,
			name_hand_request,
			name_external_request,
			name_presence_state,
			name_feedback_on,
			name_feedback_power,
			name_display_text,
			name_state,
			state_label
		)
		self._instance_logger.info(habapp_rules.core.state_machine_rule.StateMachineRule.get_initial_log_message(self))

	def _set_level_to_ventilation_items(self) -> None:
		"""Set ventilation to output item(s)."""
		habapp_rules.core.helper.send_if_different(self._item_ventilation_level, self._ventilation_level)


class VentilationHeliosTwoStage(_VentilationBase):
	""""""  # todo add text + example
	states = copy.deepcopy(_VentilationBase.states)
	__AUTO_STATE = next(state for state in states if state["name"] == "Auto")  # pragma: no cover
	__AUTO_STATE["children"].append({"name": "PowerAfterRun", "timeout": 390, "on_timeout": "_after_run_timeout"})

	trans = copy.deepcopy(_VentilationBase.trans)
	# remove not needed transitions
	trans.remove({"trigger": "_hand_on", "source": ["Auto_Normal", "Auto_PowerExternal", "Auto_LongAbsence"], "dest": "Auto_PowerHand"})  # will be extended with additional source state
	trans.remove({"trigger": "_hand_off", "source": "Auto_PowerHand", "dest": "Auto_Normal", "unless": "_external_active_and_configured"})  # this is not needed anymore since there is always Auto_PowerAfterRun after any power state
	trans.remove({"trigger": "_external_on", "source": "Auto_Normal", "dest": "Auto_PowerExternal"})  # will be extended with additional source state
	trans.remove({"trigger": "_external_off", "source": "Auto_PowerExternal", "dest": "Auto_Normal"})  # this is not needed anymore since there is always Auto_PowerAfterRun after any power state

	# add new PowerHand transitions
	trans.append({"trigger": "_hand_on", "source": ["Auto_Normal", "Auto_PowerExternal", "Auto_LongAbsence", "Auto_PowerAfterRun"], "dest": "Auto_PowerHand"})
	trans.append({"trigger": "_hand_off", "source": "Auto_PowerHand", "dest": "Auto_PowerAfterRun", "unless": "_external_active_and_configured"})

	# add new PowerExternal transitions
	trans.append({"trigger": "_external_on", "source": ["Auto_Normal", "Auto_PowerAfterRun"], "dest": "Auto_PowerExternal"})
	trans.append({"trigger": "_external_off", "source": "Auto_PowerExternal", "dest": "Auto_PowerAfterRun"})

	# add new PowerAfterRun transitions
	trans.append({"trigger": "_after_run_timeout", "source": "Auto_PowerAfterRun", "dest": "Auto_Normal"})

	# pylint: disable=too-many-arguments
	def __init__(self,
	             name_ventilation_output_on: str,
	             name_ventilation_output_power: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.ventilation.VentilationConfig,
	             name_hand_request: str | None = None,
	             name_external_request: str | None = None,
	             name_presence_state: str | None = None,
	             name_feedback_on: str | None = None,
	             name_feedback_power: str | None = None,
	             name_display_text: str | None = None,
	             after_run_timeout: int = 390,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of a Helios ventilation object which uses two switches to set the level.

		:param name_ventilation_output_on: name of OpenHAB switch item to switch on the ventilation (SwitchItem)
		:param name_ventilation_output_power: name of OpenHAB switch item to switch on the power mode (SwitchItem)
		:param name_manual: name of OpenHAB switch item to disable all automatic functions  (SwitchItem)
		:param config: configuration of the ventilation
		:param name_hand_request: name of OpenHAB switch item to enter the hand state (SwitchItem)
		:param name_external_request: name of OpenHAB switch item to enter the external state (e.g. used for dryer request) (SwitchItem)
		:param name_presence_state: name of OpenHAB presence state item (StringItem)
		:param name_feedback_on: name of OpenHAB item which shows that ventilation is on (SwitchItem)
		:param name_feedback_power: name of OpenHAB item which shows that ventilation is in power mode (SwitchItem)
		:param name_display_text: name of OpenHAB item which can be used to set the display text (e.g. for user interface) (StringItem)
		:param after_run_timeout: timeout of after-run-state in seconds
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		"""

		if not name_state:
			name_state = f"H_{name_ventilation_output_on}_state"
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_ventilation_output_on)

		# get items
		self._item_ventilation_on = HABApp.openhab.items.SwitchItem(name_ventilation_output_on)
		self._item_ventilation_power = HABApp.openhab.items.SwitchItem(name_ventilation_output_power)

		_VentilationBase.__init__(
			self,
			name_manual,
			config,
			name_hand_request,
			name_external_request,
			name_presence_state,
			name_feedback_on,
			name_feedback_power,
			name_display_text,
			name_state,
			state_label
		)

		# set timeout
		self.state_machine.get_state("Auto_PowerAfterRun").timeout = after_run_timeout

		self._instance_logger.info(habapp_rules.core.state_machine_rule.StateMachineRule.get_initial_log_message(self))

	def _get_display_text(self) -> str | None:
		"""Get Text for display.

		:return: text for display or None if not defined for this state
		"""
		if self.state == "Auto_PowerAfterRun":
			return self._config.state_after_run.display_text

		return _VentilationBase._get_display_text(self)

	def _set_level(self) -> None:
		if self.state == "Auto_PowerAfterRun":
			self._ventilation_level = 2
			self._set_level_to_ventilation_items()
			return

		super()._set_level()

	def _set_level_to_ventilation_items(self) -> None:
		"""Set ventilation to output item(s)."""
		if self.state == "Auto_PowerAfterRun":
			habapp_rules.core.helper.send_if_different(self._item_ventilation_on, "ON")
			habapp_rules.core.helper.send_if_different(self._item_ventilation_power, "OFF")

		else:
			habapp_rules.core.helper.send_if_different(self._item_ventilation_on, "ON" if self._ventilation_level else "OFF")
			habapp_rules.core.helper.send_if_different(self._item_ventilation_power, "ON" if self._ventilation_level >= 2 else "OFF")


# pylint: disable=no-member, missing-return-doc
class VentilationHeliosTwoStageHumidity(VentilationHeliosTwoStage):
	""""""  # todo add text + example
	states = copy.deepcopy(VentilationHeliosTwoStage.states)
	__AUTO_STATE = next(state for state in states if state["name"] == "Auto")  # pragma: no cover
	__AUTO_STATE["children"].append({"name": "PowerHumidity"})

	trans = copy.deepcopy(VentilationHeliosTwoStage.trans)
	# remove not needed transitions
	trans.remove({"trigger": "_after_run_timeout", "source": "Auto_PowerAfterRun", "dest": "Auto_Normal"})  # will be changed to only go to AutoNormal if the current is below the threshold (not humidity)

	# add new PowerHumidity transitions
	trans.append({"trigger": "_after_run_timeout", "source": "Auto_PowerAfterRun", "dest": "Auto_Normal", "unless": "_current_greater_threshold"})
	trans.append({"trigger": "_end_after_run", "source": "Auto_PowerAfterRun", "dest": "Auto_Normal"})
	trans.append({"trigger": "_after_run_timeout", "source": "Auto_PowerAfterRun", "dest": "Auto_PowerHumidity", "conditions": "_current_greater_threshold"})

	trans.append({"trigger": "_humidity_on", "source": "Auto_Normal", "dest": "Auto_PowerHumidity"})
	trans.append({"trigger": "_humidity_off", "source": "Auto_PowerHumidity", "dest": "Auto_Normal"})

	trans.append({"trigger": "_hand_on", "source": "Auto_PowerHumidity", "dest": "Auto_PowerHand"})
	trans.append({"trigger": "_external_on", "source": "Auto_PowerHumidity", "dest": "Auto_PowerExternal"})

	# pylint: disable=too-many-locals, too-many-arguments
	def __init__(self,
	             name_ventilation_output_on: str,
	             name_ventilation_output_power: str,
	             name_current: str,
	             name_manual: str,
	             config: habapp_rules.actors.config.ventilation.VentilationConfig,
	             name_hand_request: str | None = None,
	             name_external_request: str | None = None,
	             name_presence_state: str | None = None,
	             name_feedback_on: str | None = None,
	             name_feedback_power: str | None = None,
	             name_display_text: str | None = None,
	             after_run_timeout: int = 390,
	             current_threshold_power: float = 0.105,
	             name_state: str | None = None,
	             state_label: str | None = None) -> None:
		"""Init of a Helios ventilation object which uses two switches to set the level, including a humidity sensor.

		:param name_ventilation_output_on: name of OpenHAB switch item to switch on the ventilation (SwitchItem)
		:param name_ventilation_output_power: name of OpenHAB switch item to switch on the power mode (SwitchItem)
		:param name_current: name of OpenHAB number item which measures the current of the ventilation (NumberItem)
		:param name_manual: name of OpenHAB switch item to disable all automatic functions  (SwitchItem)
		:param config: configuration of the ventilation
		:param name_hand_request: name of OpenHAB switch item to enter the hand state (SwitchItem)
		:param name_external_request: name of OpenHAB switch item to enter the external state (e.g. used for dryer request) (SwitchItem)
		:param name_presence_state: name of OpenHAB presence state item (StringItem)
		:param name_feedback_on: name of OpenHAB item which shows that ventilation is on (SwitchItem)
		:param name_feedback_power: name of OpenHAB item which shows that ventilation is in power mode (SwitchItem)
		:param name_display_text: name of OpenHAB item which can be used to set the display text (e.g. for user interface) (StringItem)
		:param after_run_timeout: timeout of after-run-state in seconds
		:param current_threshold_power: Threshold of the current which is used in power mode (NumberItem)
		:param name_state: name of OpenHAB item for storing the current state (StringItem)
		:param state_label: label of OpenHAB item for storing the current state (StringItem)
		"""
		self._item_current = HABApp.openhab.items.NumberItem.get_item(name_current)
		self._current_threshold_power = current_threshold_power

		VentilationHeliosTwoStage.__init__(
			self,
			name_ventilation_output_on,
			name_ventilation_output_power,
			name_manual,
			config,
			name_hand_request,
			name_external_request,
			name_presence_state,
			name_feedback_on,
			name_feedback_power,
			name_display_text,
			after_run_timeout,
			name_state,
			state_label
		)

		self._item_current.listen_event(self._cb_current, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._instance_logger.info(habapp_rules.core.state_machine_rule.StateMachineRule.get_initial_log_message(self))

	def _get_initial_state(self, default_value: str = "initial") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		state = super()._get_initial_state(default_value)

		if state == "Auto_Normal" and self._current_greater_threshold():
			return "Auto_PowerHumidity"

		return state

	def _get_display_text(self) -> str | None:
		"""Get Text for display.

		:return: text for display or None if not defined for this state
		"""
		if self.state == "Auto_PowerHumidity":
			return self._config.state_humidity.display_text

		return VentilationHeliosTwoStage._get_display_text(self)

	def _set_level_to_ventilation_items(self) -> None:
		"""Set ventilation to output item(s)."""
		if self.state == "Auto_PowerExternal":
			habapp_rules.core.helper.send_if_different(self._item_ventilation_on, "ON")
			habapp_rules.core.helper.send_if_different(self._item_ventilation_power, "OFF")
		else:
			super()._set_level_to_ventilation_items()

	def _current_greater_threshold(self, current: float | None = None) -> bool:
		"""Check if current is greater than the threshold

		:param current: current which should be checked. If None the value of the current item will be taken
		:return: True if current greater than the threshold, else False
		"""
		current = current if current is not None else self._item_current.value

		if current is None:
			return False

		return current > self._current_threshold_power

	def _cb_current(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if the current changed.

		:param event: original trigger event
		"""
		if self.state != "Auto_PowerHumidity" and self._current_greater_threshold(event.value):
			self._humidity_on()
		elif self.state == "Auto_PowerHumidity" and not self._current_greater_threshold(event.value):
			self._humidity_off()
		elif self.state == "Auto_PowerAfterRun" and not self._current_greater_threshold(event.value):
			self._end_after_run()
