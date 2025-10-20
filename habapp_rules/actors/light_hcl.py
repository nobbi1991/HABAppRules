"""Light HCL rules."""

import abc
import datetime
import logging
import typing

import HABApp

import habapp_rules.actors.config.light_hcl
import habapp_rules.actors.state_observer
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.core.type_of_day
import habapp_rules.system

LOGGER = logging.getLogger(__name__)


class _HclBase(habapp_rules.core.state_machine_rule.StateMachineRule):
    """Base class for HCL rules."""

    states: typing.ClassVar = [
        {"name": "Manual"},
        {"name": "Hand", "timeout": 99, "on_timeout": "hand_timeout"},
        {
            "name": "Auto",
            "initial": "Init",
            "children": [{"name": "Init"}, {"name": "HCL"}, {"name": "Sleep", "initial": "Active", "children": [{"name": "Active"}, {"name": "Post", "timeout": 1, "on_timeout": "post_sleep_timeout"}]}, {"name": "Focus"}],
        },
    ]

    trans: typing.ClassVar = [
        {"trigger": "manual_on", "source": ["Auto", "Hand"], "dest": "Manual"},
        {"trigger": "manual_off", "source": "Manual", "dest": "Auto"},
        {"trigger": "hand_on", "source": "Auto", "dest": "Hand"},
        {"trigger": "hand_timeout", "source": "Hand", "dest": "Auto"},
        {"trigger": "sleep_start", "source": ["Auto_HCL", "Auto_Focus"], "dest": "Auto_Sleep"},
        {"trigger": "sleep_end", "source": "Auto_Sleep_Active", "dest": "Auto_Sleep_Post"},
        {"trigger": "post_sleep_timeout", "source": "Auto_Sleep_Post", "dest": "Auto_HCL"},
        {"trigger": "focus_start", "source": ["Auto_HCL", "Auto_Sleep"], "dest": "Auto_Focus"},
        {"trigger": "focus_end", "source": "Auto_Focus", "dest": "Auto_Sleep", "conditions": "_sleep_active"},
        {"trigger": "focus_end", "source": "Auto_Focus", "dest": "Auto_HCL", "unless": "_sleep_active"},
    ]

    def __init__(self, config: habapp_rules.actors.config.light_hcl.HclElevationConfig | habapp_rules.actors.config.light_hcl.HclTimeConfig) -> None:
        """Init base class.

        Args:
            config: config of HCL light.
        """
        self._config = config

        habapp_rules.core.state_machine_rule.StateMachineRule.__init__(self, self._config.items.state)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, self._config.items.color.name)

        self._state_observer = habapp_rules.actors.state_observer.StateObserverNumber(self._config.items.color.name, self._cb_hand, value_tolerance=config.parameter.color_tolerance)

        # init state machine
        self._previous_state = None
        self.state_machine = habapp_rules.core.state_machine_rule.HierarchicalStateMachineWithTimeout(model=self, states=self.states, transitions=self.trans, ignore_invalid_triggers=True, after_state_change="_update_openhab_state")
        self._set_initial_state()

        self._set_timeouts()

        # set callbacks
        self._config.items.manual.listen_event(self._cb_manual, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.sleep_state is not None:
            self._config.items.sleep_state.listen_event(self._cb_sleep, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.focus is not None:
            self._config.items.focus.listen_event(self._cb_focus, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.switch_on is not None:
            self._config.items.switch_on.listen_event(self._cb_switch_on, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _set_timeouts(self) -> None:
        """Set timeouts."""
        self.state_machine.get_state("Auto_Sleep_Post").timeout = self._config.parameter.post_sleep_timeout
        self.state_machine.get_state("Hand").timeout = self._config.parameter.hand_timeout

    def _get_initial_state(self, default_value: str = "") -> str:  # noqa: ARG002
        """Get initial state of state machine.

        Args:
            default_value: default / initial state

        Returns:
            if OpenHAB item has a state it will return it, otherwise return the given default value
        """
        if self._config.items.manual.is_on():
            return "Manual"
        if self._config.items.sleep_state is not None and self._config.items.sleep_state.value in {habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value}:
            return "Auto_Sleep"
        if self._config.items.focus is not None and self._config.items.focus.is_on():
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

    def _set_light_color(self) -> None:
        """Set light color."""
        target_color = None

        if self.state == "Auto_HCL":
            target_color = self._get_hcl_color()
        elif self.state == "Auto_Focus":
            target_color = self._config.parameter.focus_color
        elif self.state == "Auto_Sleep_Active":
            target_color = self._config.parameter.sleep_color

        if target_color is not None:
            self._state_observer.send_command(target_color)

    def on_enter_Auto_Init(self) -> None:  # noqa: N802
        """Is called on entering of init state."""
        self._set_initial_state()

    @abc.abstractmethod
    def _get_hcl_color(self) -> int | None:
        """Get HCL color.

        Returns:
            HCL light color
        """

    @staticmethod
    def _get_interpolated_value(config_start: tuple[float, float], config_end: tuple[float, float], value: float) -> float:
        """Get interpolated value.

        Args:
            config_start: start config
            config_end: end config
            value: input value which is the input for the interpolation

        Returns:
            interpolated value
        """
        fit_m = (config_end[1] - config_start[1]) / (config_end[0] - config_start[0])
        fit_t = config_end[1] - fit_m * config_end[0]

        return fit_m * value + fit_t

    def _sleep_active(self) -> bool:
        """Check if sleeping is active.

        Returns:
            True if sleeping is active, else False
        """
        if not self._config.items.sleep_state:
            return False
        return self._config.items.sleep_state.value in {habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value}

    def _cb_manual(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the manual switch has a state change event.

        Args:
            event: trigger event
        """
        if event.value == "ON":
            self.manual_on()
        else:
            self.manual_off()

    def _cb_hand(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | HABApp.openhab.events.ItemCommandEvent) -> None:  # noqa: ARG002
        """Callback, which is triggered by the state observer if a manual change was detected.

        Args:
            event: original trigger event
        """
        self._instance_logger.debug("Hand detected")
        self.hand_on()

    def _cb_focus(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the focus switch has a state change event.

        Args:
            event: trigger event
        """
        if event.value == "ON":
            self.focus_start()
        else:
            self.focus_end()

    def _cb_sleep(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the sleep state has a state change event.

        Args:
            event: trigger event
        """
        if event.value == habapp_rules.system.SleepState.PRE_SLEEPING.value:
            self.sleep_start()
            if self._config.items.focus is not None and self._config.items.focus.is_on():
                self._config.items.focus.oh_send_command("OFF")
        elif event.value == habapp_rules.system.SleepState.AWAKE.value:
            self.sleep_end()

    def _cb_switch_on(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the switch_on_item has a state change event.

        Args:
            event: trigger event
        """
        if event.value == "ON" or (isinstance(event.value, int | float) and event.value > 0):
            self._set_light_color()


class HclElevation(_HclBase):
    """Sun elevation based HCL.

    # Items:
    Number    Elevation                     "Elevation"                     {channel="astro:sun:home:position#elevation"}
    Number    HCL_Color_Elevation           "HCL Color Elevation"
    Switch    HCL_Color_Elevation_manual    "HCL Color Elevation manual"

    # Config
    config = habapp_rules.actors.config.light_hcl.HclElevationConfig(
            items=habapp_rules.actors.config.light_hcl.HclElevationItems(
                    elevation="Elevation",
                    color="HCL_Color_Elevation",
                    manual="HCL_Color_Elevation_manual",
            ),
            parameter=habapp_rules.actors.config.light_hcl.HclElevationParameter(
                    color_map=[(0, 2000), (10, 4000), (30, 5000)]
            )
    )

    # Rule init:
    habapp_rules.actors.light_hcl.HclElevation(config)
    """

    def __init__(self, config: habapp_rules.actors.config.light_hcl.HclElevationConfig) -> None:
        """Init sun elevation based HCL rule.

        Args:
            config: config for HCL rule
        """
        _HclBase.__init__(self, config)
        self._config = config

        self._config.items.elevation.listen_event(self._cb_elevation, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._cb_elevation(None)

    def _get_hcl_color(self) -> int | None:
        """Get HCL color depending on elevation.

        Returns:
            HCL light color
        """
        elevation = self._config.items.elevation.value

        if elevation is None:
            return None

        return_value = 0
        if elevation <= self._config.parameter.color_map[0][0]:
            return_value = self._config.parameter.color_map[0][1]

        elif elevation >= self._config.parameter.color_map[-1][0]:
            return_value = self._config.parameter.color_map[-1][1]

        else:
            for idx, config_itm in enumerate(self._config.parameter.color_map):  # pragma: no cover
                if config_itm[0] <= elevation <= self._config.parameter.color_map[idx + 1][0]:
                    return_value = self._get_interpolated_value(config_itm, self._config.parameter.color_map[idx + 1], elevation)
                    break

        return round(return_value)

    def _cb_elevation(self, _: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
        """Callback which is called if elevation changed."""
        if self.state == "Auto_HCL" and self._config.items.elevation.value is not None:
            self._state_observer.send_command(self._get_hcl_color())


class HclTime(_HclBase):
    """Time based HCL.

    # Items:
    Number    HCL_Color_Time           "HCL Color Time"
    Switch    HCL_Color_Time_manual    "HCL Color Time manual".

    # Config
    config = habapp_rules.actors.config.light_hcl.HclTimeConfig(
            items=habapp_rules.actors.config.light_hcl.HclTimeItems(
                    color="HCL_Color_Time",
                    manual="HCL_Color_Time_manual",
            ),
            parameter=habapp_rules.actors.config.light_hcl.HclTimeParameter(
                    [(6, 2000), (12, 4000), (20, 3000)],
            )
    )

    # Rule init:
    habapp_rules.actors.light_hcl.HclTime(config)
    """

    def __init__(self, config: habapp_rules.actors.config.light_hcl.HclTimeConfig) -> None:
        """Init time based HCL rule.

        Args:
            config: config for HCL light rule
        """
        _HclBase.__init__(self, config)
        self.run.at(self.run.trigger.interval(None, 300), self._update_color)  # every 5 minutes

    def _one_hour_later(self, current_time: datetime.datetime) -> bool:
        """Check if today the color values will be shifted one hour later in the evening.

        Args:
            current_time: current time

        Returns:
            True if next day is a weekend / holiday day
        """
        if not self._config.parameter.shift_weekend_holiday:
            return False

        if current_time.hour > 12 and (habapp_rules.core.type_of_day.is_holiday(1) or habapp_rules.core.type_of_day.is_weekend(1)):  # noqa: PLR2004
            return True
        return bool(current_time.hour <= 4 and (habapp_rules.core.type_of_day.is_holiday() or habapp_rules.core.type_of_day.is_weekend()))  # noqa: PLR2004

    def _get_hcl_color(self) -> int | None:
        """Get HCL color depending on time.

        Returns:
            HCL light color
        """
        current_time = datetime.datetime.now()

        if self._one_hour_later(current_time):
            current_time -= datetime.timedelta(hours=1)

        if current_time.hour < self._config.parameter.color_map[0][0]:
            start_config = (self._config.parameter.color_map[-1][0] - 24, self._config.parameter.color_map[-1][1])
            end_config = self._config.parameter.color_map[0]

        elif current_time.hour >= self._config.parameter.color_map[-1][0]:
            start_config = self._config.parameter.color_map[-1]
            end_config = (self._config.parameter.color_map[0][0] + 24, self._config.parameter.color_map[0][1])

        else:
            for idx, config_itm in enumerate(self._config.parameter.color_map):  # pragma: no cover
                if config_itm[0] <= current_time.hour < self._config.parameter.color_map[idx + 1][0]:
                    start_config = config_itm
                    end_config = self._config.parameter.color_map[idx + 1]
                    break

        return round(self._get_interpolated_value(start_config, end_config, current_time.hour + current_time.minute / 60))

    def _update_color(self) -> None:
        """Callback which is called every 5 minutes."""
        if self.state == "Auto_HCL":
            self._state_observer.send_command(self._get_hcl_color())
