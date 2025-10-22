"""Rules for managing motion sensors."""

import logging
import typing

import HABApp

import habapp_rules.common.hysteresis
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.sensors.config.motion
import habapp_rules.system.sleep

LOGGER = logging.getLogger(__name__)


class Motion(habapp_rules.core.state_machine_rule.StateMachineRule):
    """Class for filtering motion sensors.

    # MQTT-things:
    Thing topic Motion "Motion Sensor"{
        Channels:
        Type switch : motion        "Motion"        [stateTopic="zigbee2mqtt/Motion/occupancy", on="true", off="false"]
        Type number : brightness    "Brightness"    [stateTopic="zigbee2mqtt/Motion/illuminance_lux"]
    }

    # Items:
    Switch    Motion_raw                "Motion raw"                <motion>        {channel="mqtt:topic:broker:Motion:motion"}
    Switch    Motion_filtered           "Motion filtered"           <motion>
    Number    Motion_Brightness         "Brightness"                                {channel="mqtt:topic:broker:Motion:brightness"}
    String    I999_00_Sleeping_state    "Sleeping state"            <state>

    # Config
    config = habapp_rules.sensors.config.motion.MotionConfig(
            items=habapp_rules.sensors.config.motion.MotionItems(
                    motion_raw="Motion_raw",
                    motion_filtered="Motion_filtered",
                    brightness="Motion_Brightness",
                    sleep_state="I999_00_Sleeping_state"
            ),
            parameter=habapp_rules.sensors.config.motion.MotionParameter(
                    brightness_threshold=100,
            ),
    )

    # Rule init:
    habapp_rules.sensors.motion.Motion(config)
    """

    states: typing.ClassVar = [
        {"name": "Locked"},
        {"name": "SleepLocked"},
        {"name": "PostSleepLocked", "timeout": 99, "on_timeout": "timeout_post_sleep_locked"},
        {
            "name": "Unlocked",
            "initial": "Init",
            "children": [
                {"name": "Init"},
                {"name": "Wait"},
                {"name": "Motion"},
                {"name": "MotionExtended", "timeout": 99, "on_timeout": "timeout_motion_extended"},
                {"name": "TooBright"},
            ],
        },
    ]

    trans: typing.ClassVar = [
        # lock
        {"trigger": "lock_on", "source": ["Unlocked", "SleepLocked", "PostSleepLocked"], "dest": "Locked"},
        {"trigger": "lock_off", "source": "Locked", "dest": "Unlocked", "unless": "_sleep_active"},
        {"trigger": "lock_off", "source": "Locked", "dest": "SleepLocked", "conditions": "_sleep_active"},
        # sleep
        {"trigger": "sleep_started", "source": ["Unlocked", "PostSleepLocked"], "dest": "SleepLocked"},
        {"trigger": "sleep_end", "source": "SleepLocked", "dest": "Unlocked", "unless": "_post_sleep_lock_configured"},
        {"trigger": "sleep_end", "source": "SleepLocked", "dest": "PostSleepLocked", "conditions": "_post_sleep_lock_configured"},
        {"trigger": "timeout_post_sleep_locked", "source": "PostSleepLocked", "dest": "Unlocked", "unless": "_raw_motion_active"},
        {"trigger": "motion_off", "source": "PostSleepLocked", "dest": "PostSleepLocked"},
        {"trigger": "motion_on", "source": "PostSleepLocked", "dest": "PostSleepLocked"},
        # motion
        {"trigger": "motion_on", "source": "Unlocked_Wait", "dest": "Unlocked_Motion"},
        {"trigger": "motion_off", "source": "Unlocked_Motion", "dest": "Unlocked_MotionExtended", "conditions": "_motion_extended_configured"},
        {"trigger": "motion_off", "source": "Unlocked_Motion", "dest": "Unlocked_Wait", "unless": "_motion_extended_configured"},
        {"trigger": "timeout_motion_extended", "source": "Unlocked_MotionExtended", "dest": "Unlocked_Wait", "unless": "_brightness_over_threshold"},
        {"trigger": "timeout_motion_extended", "source": "Unlocked_MotionExtended", "dest": "Unlocked_TooBright", "conditions": "_brightness_over_threshold"},
        {"trigger": "motion_on", "source": "Unlocked_MotionExtended", "dest": "Unlocked_Motion"},
        # brightness
        {"trigger": "brightness_over_threshold", "source": "Unlocked_Wait", "dest": "Unlocked_TooBright"},
        {"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Wait", "unless": "_raw_motion_active"},
        {"trigger": "brightness_below_threshold", "source": "Unlocked_TooBright", "dest": "Unlocked_Motion", "conditions": "_raw_motion_active"},
    ]

    def __init__(self, config: habapp_rules.sensors.config.motion.MotionConfig) -> None:
        """Init of motion filter.

        Args:
            config: config for the motion filter

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationException: if configuration is not valid
        """
        self._config = config
        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.motion_raw.name)

        self._hysteresis_switch = habapp_rules.common.hysteresis.HysteresisSwitch(threshold := self._get_brightness_threshold(), threshold * 0.1 if threshold else 5) if self._config.items.brightness is not None else None

        # init state machine
        self._previous_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_initial_state()

        self.state_machine.get_state("PostSleepLocked").timeout = self._config.parameter.post_sleep_lock_time
        self.state_machine.get_state("Unlocked_MotionExtended").timeout = self._config.parameter.extended_motion_time

        # register callbacks
        self._config.items.motion_raw.listen_event(self._cb_motion_raw, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.brightness is not None:
            self._config.items.brightness.listen_event(self._cb_brightness, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.brightness_threshold is not None:
            self._config.items.brightness_threshold.listen_event(self._cb_threshold_change, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.lock is not None:
            self._config.items.lock.listen_event(self._cb_lock, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.sleep_state is not None:
            self._config.items.sleep_state.listen_event(self._cb_sleep, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._instance_logger.debug(super().get_initial_log_message())

    def _get_initial_state(self, default_value: str = "initial") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        if self._config.items.lock is not None and self._config.items.lock.is_on():
            return "Locked"
        if self._config.items.sleep_state is not None and self._config.items.sleep_state.value == habapp_rules.system.SleepState.SLEEPING.value:
            return "SleepLocked"
        if self._config.items.brightness is not None and self._brightness_over_threshold():
            return "Unlocked_TooBright"
        if self._config.items.motion_raw.is_on():
            return "Unlocked_Motion"
        return "Unlocked_Wait"

    def _update_openhab_state(self) -> None:
        """Update OpenHAB state item. This should method should be set to "after_state_change" of the state machine."""
        if self.state != self._previous_state:
            super()._update_openhab_state()
            self.__send_filtered_motion()

            self._instance_logger.debug(f"State change: {self._previous_state} -> {self.state}")
            self._previous_state = self.state

    def __send_filtered_motion(self) -> None:
        """Send filtered motion state to OpenHAB item."""
        target_state = "ON" if self.state in {"Unlocked_Motion", "Unlocked_MotionExtended"} else "OFF"
        if target_state != self._config.items.motion_filtered.value:
            self._config.items.motion_filtered.oh_send_command(target_state)

    def _raw_motion_active(self) -> bool:
        """Check if raw motion is active.

        Returns:
            True if active, else False
        """
        return bool(self._config.items.motion_raw)

    def _brightness_over_threshold(self) -> bool:
        """Check if brightness is over threshold.

        Returns:
             True if active, else False
        """
        return self._hysteresis_switch.get_output(self._config.items.brightness.value)

    def _motion_extended_configured(self) -> bool:
        """Check if extended motion is configured.

        Returns:
            True if active, else False
        """
        return self._config.parameter.extended_motion_time > 0

    def _post_sleep_lock_configured(self) -> bool:
        """Check if post sleep lock is configured.

        Returns:
             rue if active, else False
        """
        return self._config.parameter.post_sleep_lock_time > 0

    def _sleep_active(self) -> bool:
        """Check if sleeping is active.

        Returns:
            True if sleeping is active, else False
        """
        return self._config.items.sleep_state.value == habapp_rules.system.SleepState.SLEEPING.value

    def _get_brightness_threshold(self) -> float:
        """Get the current brightness threshold value.

        Returns:
            brightness threshold

        Raises:
            habapp_rules.core.exceptions.HabAppRulesError: if brightness value not given by item or value
        """
        if self._config.parameter.brightness_threshold:
            return self._config.parameter.brightness_threshold
        if self._config.items.brightness_threshold is not None:
            return value if (value := self._config.items.brightness_threshold.value) else float("inf")
        msg = f"Can not get brightness threshold. Brightness value or item is not given. value: {self._config.parameter.brightness_threshold} | item: {self._config.items.brightness_threshold}"
        raise habapp_rules.core.exceptions.HabAppRulesError(msg)

    def on_enter_Unlocked_Init(self) -> None:  # noqa: N802
        """Callback, which is called on enter of Unlocked_Init state."""
        if self._config.items.brightness is not None and self._brightness_over_threshold():
            self.to_Unlocked_TooBright()
        elif self._config.items.motion_raw.is_on():
            self.to_Unlocked_Motion()
        else:
            self.to_Unlocked_Wait()

    def _check_brightness(self, value: float | None = None) -> None:
        """Check if brightness is higher than the threshold and trigger the class methods.

        Args:
            value: Value to check. None if last value should be used
        """
        if self._hysteresis_switch.get_output(value):
            self.brightness_over_threshold()
        else:
            self.brightness_below_threshold()

    def _cb_threshold_change(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the brightness threshold state changed.

        Args:
            event: trigger event
        """
        self._hysteresis_switch.set_threshold_on(event.value)
        self._check_brightness()

    def _cb_motion_raw(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the raw motion state changed.

        Args:
            event: trigger event
        """
        if event.value == "ON":
            self.motion_on()
        else:
            self.motion_off()

    def _cb_brightness(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the brightness state changed.

        Args:
            event: trigger event
        """
        self._check_brightness(event.value)

    def _cb_lock(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the lock state changed.

        Args:
            event: trigger event
        """
        if event.value == "ON":
            self.lock_on()
        else:
            self.lock_off()

    def _cb_sleep(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the sleep state changed.

        Args:
            event: trigger event
        """
        if event.value == habapp_rules.system.SleepState.SLEEPING.value:
            self.sleep_started()
        if event.value == habapp_rules.system.SleepState.AWAKE.value:
            self.sleep_end()
