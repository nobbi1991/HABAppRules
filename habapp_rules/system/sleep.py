"""Rule to set/unset sleep state."""

import datetime
import typing

from HABApp.openhab.events import ItemStateChangedEvent
from HABApp.openhab.events.event_filters import ItemStateChangedEventFilter

from habapp_rules.core.base import RuleBase
from habapp_rules.core.helper import send_if_different
from habapp_rules.core.state_machine_rule import StateMachineRule, StateMachineWithTimeout
from habapp_rules.system.config.sleep import LinkSleepConfig, SleepConfig


class Sleep(StateMachineRule):
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
    config = SleepConfig(
            items=SleepItems(
                    sleep="I01_02_Sleep",
                    sleep_req="I01_02_Sleep_req",
                    state="I01_02_Sleep_State",
                    lock="I01_02_Sleep_lock",
                    lock_req="I01_02_Sleep_lock_req",
                    display_text="I01_02_Sleep_text"
            )
    )

    # Rule init:
    Sleep(config)
    """

    states: typing.ClassVar = [
        {"name": "Awake"},
        {"name": "PreSleeping", "timeout": 3, "on_timeout": "PreSleeping_timeout"},
        {"name": "Sleeping"},
        {"name": "PostSleeping", "timeout": 3, "on_timeout": "PostSleeping_timeout"},
        {"name": "Locked"},
    ]

    trans: typing.ClassVar = [
        {"trigger": "start_Sleeping", "source": ["Awake", "PostSleeping"], "dest": "PreSleeping"},
        {"trigger": "PreSleeping_timeout", "source": "PreSleeping", "dest": "Sleeping"},
        {"trigger": "end_Sleeping", "source": "Sleeping", "dest": "PostSleeping"},
        {"trigger": "end_Sleeping", "source": "PreSleeping", "dest": "Awake", "unless": "lock_request_active"},
        {"trigger": "end_Sleeping", "source": "PreSleeping", "dest": "Locked", "conditions": "lock_request_active"},
        {"trigger": "PostSleeping_timeout", "source": "PostSleeping", "dest": "Awake", "unless": "lock_request_active"},
        {"trigger": "PostSleeping_timeout", "source": "PostSleeping", "dest": "Locked", "conditions": "lock_request_active"},
        {"trigger": "set_lock", "source": "Awake", "dest": "Locked"},
        {"trigger": "release_lock", "source": "Locked", "dest": "Awake"},
    ]

    def __init__(self, config: SleepConfig) -> None:
        """Init of Sleep object.

        Args:
            config: config for Sleeping state
        """
        self._config = config
        StateMachineRule.__init__(self, config.items.state, config.items.sleep.name)

        # init attributes
        self._sleep_request_active = config.items.sleep_request.is_on()
        self._lock_request_active = config.items.lock_request.is_on() if config.items.lock_request is not None else False

        # init state machine
        self.state_machine = StateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state", initial=self._get_initial_state())

        # add callbacks
        config.items.sleep_request.listen_event(self._cb_sleep_request, ItemStateChangedEventFilter())
        if config.items.lock_request is not None:
            config.items.lock_request.listen_event(self._cb_lock_request, ItemStateChangedEventFilter())

        self._post_init()

    def _get_initial_state(self, default_value: str = "Awake") -> str:
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            return correct state if it could be detected, if not return default value
        """
        sleep_req = self._config.items.sleep_request.is_on() if self._config.items.sleep_request.value is not None else None
        lock_req = self._config.items.lock_request.is_on() if self._config.items.lock_request is not None and self._config.items.lock_request.value is not None else None

        if sleep_req:
            return "Sleeping"
        if lock_req:
            return "Locked"
        if sleep_req is False:
            return "Awake"

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
        if self.state in {"PreSleeping", "Sleeping"}:
            send_if_different(self._config.items.sleep, "ON")
        else:
            send_if_different(self._config.items.sleep, "OFF")

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
        if self.state == "Awake":
            return "Schlafen"
        if self.state == "PreSleeping":
            return "Guten Schlaf"
        if self.state == "Sleeping":
            return "Aufstehen"
        if self.state == "PostSleeping":
            return "Guten Morgen"
        if self.state == "Locked":
            return "Gesperrt"
        return ""

    def __update_lock_state(self) -> None:
        """Update the return lock state value of OpenHAB item."""
        if self._config.items.lock is not None:
            if self.state in {"PreSleeping", "PostSleeping", "Locked"}:
                send_if_different(self._config.items.lock, "ON")
            else:
                send_if_different(self._config.items.lock, "OFF")

    def _cb_sleep_request(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is called if sleep request item changed state.

        Args:
            event: Item state change event of sleep_request item
        """
        if event.value == "ON" and self.state in {"Awake", "PostSleeping"}:
            self._instance_logger.debug("Start Sleeping through sleep switch")
            self._sleep_request_active = True
            self.trigger("start_Sleeping")
        elif event.value == "ON" and self.state == "Locked":
            self._sleep_request_active = False
            self._config.items.sleep_request.oh_send_command("OFF")
        elif event.value == "OFF" and self.state in {"Sleeping", "PreSleeping"}:
            self._instance_logger.debug("End Sleeping through sleep switch")
            self._sleep_request_active = True
            self.trigger("end_Sleeping")

    def _cb_lock_request(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is called if lock request item changed state.

        Args:
            event: Item state change event of sleep_request item
        """
        self._lock_request_active = event.value == "ON"

        if self.state == "Awake" and event.value == "ON":
            self.trigger("set_lock")
        elif self.state == "Locked" and event.value == "OFF":
            self.trigger("release_lock")
        else:
            self.__update_lock_state()


class LinkSleep(RuleBase):
    """Link sleep items depending on current time."""

    def __init__(self, config: LinkSleepConfig) -> None:
        """Init rule.

        Args:
            config: Config for linking sleep rules
        """
        self._config = config
        RuleBase.__init__(self, config.items.sleep_master.name)

        config.items.sleep_master.listen_event(self._cb_master, ItemStateChangedEventFilter())

        if config.items.link_active_feedback is not None:
            self.run.at(self.run.trigger.time(config.parameter.link_time_start), self._set_link_active_feedback, target_state="ON")
            self.run.at(self.run.trigger.time(config.parameter.link_time_end), self._set_link_active_feedback, target_state="OFF")
            self.run.soon(self._set_link_active_feedback, target_state=self._check_time_in_window)

        self._log_init_done()

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

    def _cb_master(self, event: ItemStateChangedEvent) -> None:
        """Callback which is triggered if the state of the master item changes.

        Args:
            event: state change event
        """
        if not self._check_time_in_window():
            return

        self._instance_logger.debug(f"Set request of all linked sleep states of {self._config.items.sleep_master.name}")
        for itm in self._config.items.sleep_request_slaves:
            send_if_different(itm, event.value)

    def _set_link_active_feedback(self, target_state: str) -> None:
        """Set feedback for link is active.

        Args:
            target_state: Target state which should be set ["ON" / "OFF"]
        """
        self._config.items.link_active_feedback.oh_send_command(target_state)  # type: ignore[union-attr]  # _set_link_active_feedback is only called if item is set
