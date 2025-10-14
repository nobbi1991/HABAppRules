"""Rule to set/unset sleep state."""

import datetime
import logging
import typing

import HABApp.openhab.events
import HABApp.util

import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system.config.sleep

LOGGER = logging.getLogger(__name__)


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
    Switch    I01_02_Sleep              "Sleep"                     <moon>     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep_RM"}
    Switch    I01_02_Sleep_req          "Sleep request"             <moon>     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep"}
    String    I01_02_Sleep_text         "Text for display"                     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep_text"}
    Switch    I01_02_Sleep_lock         "Lock"                      <lock>     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep_lock_RM"}
    Switch    I01_02_Sleep_lock_req     "Lock request"              <lock>     {channel="knx:device:bridge:T00_99_OpenHab_Sleep:sleep_lock"}
    String    I01_02_Sleep_State        "State"                     <state>

    # Config:
    config = habapp_rules.system.config.sleep.SleepConfig(
            items=habapp_rules.system.config.sleep.SleepItems(
                    sleep="I01_02_Sleep",
                    sleep_req="I01_02_Sleep_req",
                    state="I01_02_Sleep_State",
                    lock="I01_02_Sleep_lock",
                    lock_req="I01_02_Sleep_lock_req",
                    display_text="I01_02_Sleep_text"
            )
    )

    # Rule init:
    habapp_rules.system.sleep.Sleep(config)
    """

    states: typing.ClassVar = [
        {"name": "awake"},
        {"name": "pre_sleeping", "timeout": 3, "on_timeout": "pre_sleeping_timeout"},
        {"name": "sleeping"},
        {"name": "post_sleeping", "timeout": 3, "on_timeout": "post_sleeping_timeout"},
        {"name": "locked"},
    ]

    trans: typing.ClassVar = [
        {"trigger": "start_sleeping", "source": ["awake", "post_sleeping"], "dest": "pre_sleeping"},
        {"trigger": "pre_sleeping_timeout", "source": "pre_sleeping", "dest": "sleeping"},
        {"trigger": "end_sleeping", "source": "sleeping", "dest": "post_sleeping"},
        {"trigger": "end_sleeping", "source": "pre_sleeping", "dest": "awake", "unless": "lock_request_active"},
        {"trigger": "end_sleeping", "source": "pre_sleeping", "dest": "locked", "conditions": "lock_request_active"},
        {"trigger": "post_sleeping_timeout", "source": "post_sleeping", "dest": "awake", "unless": "lock_request_active"},
        {"trigger": "post_sleeping_timeout", "source": "post_sleeping", "dest": "locked", "conditions": "lock_request_active"},
        {"trigger": "set_lock", "source": "awake", "dest": "locked"},
        {"trigger": "release_lock", "source": "locked", "dest": "awake"},
    ]

    def __init__(self, config: habapp_rules.system.config.sleep.SleepConfig) -> None:
        """Init of Sleep object.

        Args:
            config: config for sleeping state
        """
        self._config = config
        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, config.items.sleep.name)

        # init attributes
        self._sleep_request_active = config.items.sleep_request.is_on()
        self._lock_request_active = config.items.lock_request.is_on() if config.items.lock_request is not None else False

        # init state machine
        self.state_machine = habapp_rules.core.state_machine_rule.StateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_initial_state()

        self._update_openhab_state()

        # add callbacks
        config.items.sleep_request.listen_event(self._cb_sleep_request, HABApp.openhab.events.ItemStateChangedEventFilter())
        if config.items.lock_request is not None:
            config.items.lock_request.listen_event(self._cb_lock_request, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._instance_logger.debug(super().get_initial_log_message())

    def _get_initial_state(self, default_value: str = "awake") -> str:
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            return correct state if it could be detected, if not return default value
        """
        sleep_req = self._config.items.sleep_request.is_on() if self._config.items.sleep_request.value is not None else None
        lock_req = self._config.items.lock_request.is_on() if self._config.items.lock_request is not None and self._config.items.lock_request.value is not None else None

        if sleep_req:
            return "sleeping"
        if lock_req:
            return "locked"
        if sleep_req is False:
            return "awake"

        return default_value

    @property
    def sleep_request_active(self) -> bool:
        """Check if a sleep request is active.

        Returns:
            return true if lock request is active
        """
        return self._sleep_request_active

    @property
    def lock_request_active(self) -> bool:
        """Check if a lock request is active.

        Returns:
            return true if lock request is active
        """
        return self._lock_request_active

    def _update_openhab_state(self) -> None:
        """Extend _update_openhab state of base class to also update other OpenHAB items."""
        super()._update_openhab_state()

        # update sleep state
        if self.state in {"pre_sleeping", "sleeping"}:
            habapp_rules.core.helper.send_if_different(self._config.items.sleep, "ON")
        else:
            habapp_rules.core.helper.send_if_different(self._config.items.sleep, "OFF")

        # update lock state
        self.__update_lock_state()

        # update display text
        if self._config.items.display_text is not None:
            self._config.items.display_text.oh_send_command(self.__get_display_text())

    def __get_display_text(self) -> str:
        """Get Text for displays.

        Returns:
            display text
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

    def __update_lock_state(self) -> None:
        """Update the return lock state value of OpenHAB item."""
        if self._config.items.lock is not None:
            if self.state in {"pre_sleeping", "post_sleeping", "locked"}:
                habapp_rules.core.helper.send_if_different(self._config.items.lock, "ON")
            else:
                habapp_rules.core.helper.send_if_different(self._config.items.lock, "OFF")

    def _cb_sleep_request(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if sleep request item changed state.

        Args:
            event: Item state change event of sleep_request item
        """
        if event.value == "ON" and self.state in {"awake", "post_sleeping"}:
            self._instance_logger.debug("Start sleeping through sleep switch")
            self._sleep_request_active = True
            self.start_sleeping()
        elif event.value == "ON" and self.state == "locked":
            self._sleep_request_active = False
            self._config.items.sleep_request.oh_send_command("OFF")
        elif event.value == "OFF" and self.state in {"sleeping", "pre_sleeping"}:
            self._instance_logger.debug("End sleeping through sleep switch")
            self._sleep_request_active = True
            self.end_sleeping()

    def _cb_lock_request(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if lock request item changed state.

        Args:
            event: Item state change event of sleep_request item
        """
        self._lock_request_active = event.value == "ON"

        if self.state == "awake" and event.value == "ON":
            self.set_lock()
        elif self.state == "locked" and event.value == "OFF":
            self.release_lock()
        else:
            self.__update_lock_state()


class LinkSleep(HABApp.Rule):
    """Link sleep items depending on current time."""

    def __init__(self, config: habapp_rules.system.config.sleep.LinkSleepConfig) -> None:
        """Init rule.

        Args:
            config: Config for linking sleep rules
        """
        self._config = config
        HABApp.Rule.__init__(self)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self.rule_name)

        config.items.sleep_master.listen_event(self._cb_master, HABApp.openhab.events.ItemStateChangedEventFilter())

        if config.items.link_active_feedback is not None:
            self.run.at(self.run.trigger.time(config.parameter.link_time_start), self._set_link_active_feedback, target_state="ON")
            self.run.at(self.run.trigger.time(config.parameter.link_time_end), self._set_link_active_feedback, target_state="OFF")
            self.run.soon(self._set_link_active_feedback, target_state=self._check_time_in_window())

    def _check_time_in_window(self) -> bool:
        """Check if current time is in the active time window.

        Returns:
            True if current time is in time the active time window
        """
        now = datetime.datetime.now().time()

        if self._config.parameter.link_time_start <= self._config.parameter.link_time_end:
            return self._config.parameter.link_time_start <= now <= self._config.parameter.link_time_end
        # cross midnight
        return self._config.parameter.link_time_start <= now or now <= self._config.parameter.link_time_end

    def _cb_master(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if the state of the master item changes.

        Args:
            event: state change event
        """
        if not self._check_time_in_window():
            return

        self._instance_logger.debug(f"Set request of all linked sleep states of {self._config.items.sleep_master.name}")
        for itm in self._config.items.sleep_request_slaves:
            habapp_rules.core.helper.send_if_different(itm, event.value)

    def _set_link_active_feedback(self, target_state: str) -> None:
        """Set feedback for link is active.

        Args:
            target_state: Target state which should be set ["ON" / "OFF"]
        """
        self._config.items.link_active_feedback.oh_send_command(target_state)
