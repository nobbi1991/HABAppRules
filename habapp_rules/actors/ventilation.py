"""Ventilation rules."""

import abc
import copy
import datetime
import logging
import typing

import HABApp

import habapp_rules.actors.config.ventilation
import habapp_rules.core.exceptions
import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system
from habapp_rules.actors.config.ventilation import VentilationTwoStageItems
from habapp_rules.core.helper import send_if_different

LOGGER = logging.getLogger(__name__)

LEVEL_POWER = 2


def _to_datetime(time_input: datetime.time) -> datetime.datetime:  # this is needed because of https://github.com/spacemanspiff2007/eascheduler/issues
    """Converts a datetime.time object to a datetime.datetime object using today's date. Adds one day if the time is in the past.

    Args:
        time_input: The time to convert.

    Returns:
        The resulting datetime object with today's date or the next day if the time is in the past.
    """
    result = datetime.datetime.combine(datetime.datetime.now(), time_input)

    # If the resulting datetime is in the past, add one day
    if result <= datetime.datetime.now():
        result += datetime.timedelta(days=1)

    return result


class _VentilationBase(habapp_rules.core.state_machine_rule.StateMachineRule):
    """Class for ventilation objects."""

    _config: VentilationTwoStageItems

    states: typing.ClassVar = [
        {"name": "Manual"},
        {
            "name": "Auto",
            "initial": "Init",
            "children": [
                {"name": "Init"},
                {"name": "Normal"},
                {"name": "PowerHand", "timeout": 3600, "on_timeout": "_hand_off"},
                {"name": "PowerExternal"},
                {"name": "LongAbsence", "initial": "Off", "children": [{"name": "On", "timeout": 3600, "on_timeout": "_long_absence_power_off"}, {"name": "Off"}]},
            ],
        },
    ]

    trans: typing.ClassVar = [
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

    def __init__(self, config: habapp_rules.actors.config.ventilation.VentilationConfig) -> None:
        """Init of ventilation base.

        Args:
            config: ventilation config
        """
        self._config = config
        self._ventilation_level: int | None = None

        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)

        # init state machine
        self._previous_state = None
        self._state_change_time = datetime.datetime.now()
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_initial_state()

        self._apply_config()

        # callbacks
        self._config.items.manual.listen_event(self._cb_manual, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.hand_request is not None:
            self._config.items.hand_request.listen_event(self._cb_power_hand_request, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.external_request is not None:
            self._config.items.external_request.listen_event(self._cb_external_request, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.presence_state is not None:
            self._config.items.presence_state.listen_event(self._cb_presence_state, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._update_openhab_state()

    def _get_initial_state(self, default_value: str = "initial") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        if self._config.items.manual.is_on():
            return "Manual"
        if self._config.items.hand_request is not None and self._config.items.hand_request.is_on():
            return "Auto_PowerHand"
        if self._config.items.presence_state is not None and self._config.items.presence_state.value == habapp_rules.system.PresenceState.LONG_ABSENCE.value:
            return "Auto_LongAbsence"
        if self._config.items.external_request is not None and self._config.items.external_request.is_on():
            return "Auto_PowerExternal"
        return "Auto_Normal"

    def _apply_config(self) -> None:
        """Apply values from config."""
        self.state_machine.get_state("Auto_PowerHand").timeout = self._config.parameter.state_hand.timeout
        self.state_machine.get_state("Auto_LongAbsence_On").timeout = self._config.parameter.state_long_absence.duration

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
        """Set ventilation level."""
        if self.state == "Manual":
            return

        if self.state == "Auto_PowerHand":
            self._ventilation_level = self._config.parameter.state_hand.level
        elif self.state == "Auto_Normal":
            self._ventilation_level = self._config.parameter.state_normal.level
        elif self.state == "Auto_PowerExternal":
            self._ventilation_level = self._config.parameter.state_external.level
        elif self.state == "Auto_LongAbsence_On":
            self._ventilation_level = self._config.parameter.state_long_absence.level
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

        Returns:
             text for display or None if not defined for this state
        """
        if self.state == "Manual":
            return "Manual"
        if self.state == "Auto_Normal":
            return self._config.parameter.state_normal.display_text
        if self.state == "Auto_PowerExternal":
            return self._config.parameter.state_external.display_text
        if self.state == "Auto_LongAbsence_On":
            return f"{self._config.parameter.state_long_absence.display_text} ON"
        if self.state == "Auto_LongAbsence_Off":
            return f"{self._config.parameter.state_long_absence.display_text} OFF"

        return None

    def _set_feedback_states(self) -> None:
        """Set feedback sates to the OpenHAB items."""
        if self._config.items.hand_request is not None and self._previous_state == "Auto_PowerHand":
            habapp_rules.core.helper.send_if_different(self._config.items.hand_request, "OFF")

        if self._config.items.feedback_on is not None:
            habapp_rules.core.helper.send_if_different(self._config.items.feedback_on, "ON" if self._ventilation_level else "OFF")

        if self._config.items.feedback_power is not None:
            target_value = "ON" if self._ventilation_level is not None and self._ventilation_level >= LEVEL_POWER else "OFF"
            habapp_rules.core.helper.send_if_different(self._config.items.feedback_power, target_value)

        if self._config.items.display_text is not None:
            if self.state == "Auto_PowerHand":
                self.__set_hand_display_text()
                return

            if (display_text := self._get_display_text()) is not None:
                habapp_rules.core.helper.send_if_different(self._config.items.display_text, display_text)

    def __set_hand_display_text(self) -> None:
        """Callback to set display text."""
        if self.state != "Auto_PowerHand":
            # state changed and is not PowerHand anymore
            return

        # get the remaining minutes and set display text
        remaining_minutes = round((self._config.parameter.state_hand.timeout - (datetime.datetime.now() - self._state_change_time).seconds) / 60)
        remaining_minutes = max(remaining_minutes, 0)
        habapp_rules.core.helper.send_if_different(self._config.items.display_text, f"{self._config.parameter.state_hand.display_text} {remaining_minutes}min")

        # re-trigger this method in 1 minute
        self.run.once(60, self.__set_hand_display_text)

    def on_enter_Auto_Init(self) -> None:  # noqa: N802
        """Is called on entering of Auto_Init state."""
        self._set_initial_state()

    def on_enter_Auto_LongAbsence_Off(self) -> None:  # noqa: N802
        """Is called on entering of Auto_LongAbsence_Off state."""
        trigger_time = _to_datetime(self._config.parameter.state_long_absence.start_time)
        self.run.once(trigger_time, self._trigger_long_absence_power_on)

    def _trigger_long_absence_power_on(self) -> None:
        """Trigger long absence power on."""
        self._long_absence_power_on()

    def _external_active_and_configured(self) -> bool:
        """Check if external request is active and configured.

        Returns:
            True if external request is active and configured
        """
        return self._config.items.external_request is not None and self._config.items.external_request.is_on()

    def _cb_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if manual mode changed.

        Args:
            event: original trigger event
        """
        if event.value == "ON":
            self._manual_on()
        else:
            self._manual_off()

    def _cb_power_hand_request(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if power_hand_request changed.

        Args:
            event: original trigger event
        """
        if event.value == "ON":
            self._hand_on()
        else:
            self._hand_off()

    def _cb_external_request(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if external request changed.

        Args:
            event: original trigger event
        """
        if event.value == "ON":
            self._external_on()
        else:
            self._external_off()

    def _cb_presence_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if presence_state changed.

        Args:
            event: original trigger event
        """
        if event.value == habapp_rules.system.PresenceState.LONG_ABSENCE.value:
            self._long_absence_on()
        else:
            self._long_absence_off()


class Ventilation(_VentilationBase):
    """Rule for managing ventilation systems which can be controlled with ventilation levels.

    # Items:
    Number  Ventilation_level           "Ventilation level"
    Switch  Manual                      "Manual"
    Switch  Hand_Request                "Hand request"
    Switch  External_Request            "External request"
    String  presence_state              "Presence state"
    Switch  Feedback_On                 "Feedback is ON"
    Switch  Feedback_Power              "Feedback is Power"

    # Config
    config = habapp_rules.actors.config.ventilation.VentilationConfig(
            items=habapp_rules.actors.config.ventilation.VentilationItems(
                    ventilation_level="Ventilation_level",
                    manual="Manual",
                    hand_request="Hand_Request",
                    external_request="External_Request",
                    presence_state="presence_state",
                    feedback_on="Feedback_On",
                    feedback_power="Feedback_Power"
            )
    )

    # Rule init:
    habapp_rules.actors.ventilation.Ventilation(config)
    """

    def __init__(self, config: habapp_rules.actors.config.ventilation.VentilationConfig) -> None:
        """Init of ventilation object.

        Args:
            config: config of the ventilation rule
        """
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, config.items.ventilation_level.name)

        _VentilationBase.__init__(self, config)
        self._instance_logger.info(habapp_rules.core.state_machine_rule.StateMachineRule.get_initial_log_message(self))

    def _set_level_to_ventilation_items(self) -> None:
        """Set ventilation to output item(s)."""
        habapp_rules.core.helper.send_if_different(self._config.items.ventilation_level, self._ventilation_level)


class VentilationHeliosTwoStage(_VentilationBase):
    """Rule for managing Helios ventilation systems with humidity sensor (E.g. Helios ELS).

    # Items:
    Switch  Ventilation_Switch_On       "Ventilation relay on"
    Switch  Ventilation_Switch_Power    "Ventilation relay power"
    Switch  Manual                      "Manual"
    Switch  Hand_Request                "Hand request"
    Switch  External_Request            "External request"
    String  presence_state              "Presence state"
    Switch  Feedback_On                 "Feedback is ON"
    Switch  Feedback_Power              "Feedback is Power"

    # Config
    config = habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
            items=habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
                    ventilation_output_on="Ventilation_Switch_On",
                    ventilation_output_power="Ventilation_Switch_Power",
                    manual="Manual",
                    hand_request="Hand_Request",
                    external_request="External_Request",
                    presence_state="presence_state",
                    feedback_on="Feedback_On",
                    feedback_power="Feedback_Power"
            )
    )

    # Rule init:
    habapp_rules.actors.ventilation.VentilationHeliosTwoStage(config)
    """

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

    def __init__(self, config: habapp_rules.actors.config.ventilation.VentilationTwoStageConfig) -> None:
        """Init of a Helios ventilation object which uses two switches to set the level.

        Args:
            config: config for the ventilation rule
        """
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, config.items.ventilation_output_on.name)
        _VentilationBase.__init__(self, config)

        # set timeout
        self.state_machine.get_state("Auto_PowerAfterRun").timeout = config.parameter.after_run_timeout

        self._instance_logger.info(habapp_rules.core.state_machine_rule.StateMachineRule.get_initial_log_message(self))

    def _get_display_text(self) -> str | None:
        """Get Text for display.

        Returns:
            text for display or None if not defined for this state
        """
        if self.state == "Auto_PowerAfterRun":
            return self._config.parameter.state_after_run.display_text

        return _VentilationBase._get_display_text(self)  # noqa: SLF001

    def _set_level(self) -> None:
        """Set ventilation level."""
        if self.state == "Auto_PowerAfterRun":
            self._ventilation_level = self._config.parameter.state_after_run.level
            self._set_level_to_ventilation_items()

        else:
            super()._set_level()

        if self._config.items.feedback_ventilation_level is not None:
            send_if_different(self._config.items.feedback_ventilation_level, self._ventilation_level)

    def _set_level_to_ventilation_items(self) -> None:
        """Set ventilation to output item(s)."""
        if self.state == "Auto_PowerAfterRun":
            habapp_rules.core.helper.send_if_different(self._config.items.ventilation_output_on, "ON")
            habapp_rules.core.helper.send_if_different(self._config.items.ventilation_output_power, "OFF")

        else:
            habapp_rules.core.helper.send_if_different(self._config.items.ventilation_output_on, "ON" if self._ventilation_level else "OFF")
            habapp_rules.core.helper.send_if_different(self._config.items.ventilation_output_power, "ON" if self._ventilation_level >= LEVEL_POWER else "OFF")


class VentilationHeliosTwoStageHumidity(VentilationHeliosTwoStage):
    """Rule for managing Helios ventilation systems with humidity sensor (E.g. Helios ELS).

    # Items:
    Switch  Ventilation_Switch_On       "Ventilation relay on"
    Switch  Ventilation_Switch_Power    "Ventilation relay power"
    Number  Ventilation_Current         "Ventilation current"
    Switch  Manual                      "Manual"
    Switch  Hand_Request                "Hand request"
    Switch  External_Request            "External request"
    String  presence_state              "Presence state"
    Switch  Feedback_On                 "Feedback is ON"
    Switch  Feedback_Power              "Feedback is Power"

    # Config
    config = habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
            items=habapp_rules.actors.config.ventilation.VentilationTwoStageItems(
                    ventilation_output_on="Ventilation_Switch_On",
                    ventilation_output_power="Ventilation_Switch_Power",
                    current="Ventilation_Current",
                    manual="Manual",
                    hand_request="Hand_Request",
                    external_request="External_Request",
                    presence_state="presence_state",
                    feedback_on="Feedback_On",
                    feedback_power="Feedback_Power"
            )
    )

    # Rule init:
    habapp_rules.actors.ventilation.VentilationHeliosTwoStageHumidity(config)
    """

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

    def __init__(self, config: habapp_rules.actors.config.ventilation.VentilationTwoStageConfig) -> None:
        """Init of a Helios ventilation object which uses two switches to set the level, including a humidity sensor.

        Args:
            config: configuration of the ventilation rule

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationError: if config is missing required items
        """
        if config.items.current is None:
            msg = "Missing item 'current'"
            raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)
        self._current_threshold_power = config.parameter.current_threshold_power

        VentilationHeliosTwoStage.__init__(self, config)
        config.items.current.listen_event(self._cb_current, HABApp.openhab.events.ItemStateUpdatedEventFilter())

    def _get_initial_state(self, default_value: str = "initial") -> str:
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        state = super()._get_initial_state(default_value)

        if state == "Auto_Normal" and self._current_greater_threshold():
            return "Auto_PowerHumidity"

        return state

    def _get_display_text(self) -> str | None:
        """Get Text for display.

        Returns:
            text for display or None if not defined for this state
        """
        if self.state == "Auto_PowerHumidity":
            return self._config.parameter.state_humidity.display_text

        return VentilationHeliosTwoStage._get_display_text(self)  # noqa: SLF001

    def _set_level(self) -> None:
        """Set ventilation level."""
        if self.state == "Auto_PowerHumidity":
            self._ventilation_level = self._config.parameter.state_humidity.level
            self._set_level_to_ventilation_items()
            return

        super()._set_level()

    def _set_level_to_ventilation_items(self) -> None:
        """Set ventilation to output item(s)."""
        if self.state == "Auto_PowerHumidity":
            habapp_rules.core.helper.send_if_different(self._config.items.ventilation_output_on, "ON")
            habapp_rules.core.helper.send_if_different(self._config.items.ventilation_output_power, "OFF")
        else:
            super()._set_level_to_ventilation_items()

    def _current_greater_threshold(self, current: float | None = None) -> bool:
        """Check if current is greater than the threshold.

        Args:
            current: current which should be checked. If None the value of the current item will be taken

        Returns:
            True if current greater than the threshold, else False
        """
        current = current if current is not None else self._config.items.current.value

        if current is None:
            return False

        return current > self._current_threshold_power

    def _cb_current(self, event: HABApp.openhab.events.ItemStateUpdatedEvent) -> None:
        """Callback which is triggered if the current changed.

        Args:
            event: original trigger event
        """
        if self.state != "Auto_PowerHumidity" and self._current_greater_threshold(event.value):
            self._humidity_on()
        elif self.state == "Auto_PowerHumidity" and not self._current_greater_threshold(event.value):
            self._humidity_off()
        elif self.state == "Auto_PowerAfterRun" and not self._current_greater_threshold(event.value):
            self._end_after_run()
