"""Heating rules."""

import logging

import HABApp

import habapp_rules.actors.config.heating
from habapp_rules.core.helper import send_if_different

LOGGER = logging.getLogger(__name__)


class KnxHeating(HABApp.Rule):
    """Rule which can be used to control a heating actor which only supports temperature offsets (e.g. MDT).

    This rule uses a virtual temperature OpenHAB item for the target temperature. If this changes, the new offset is calculated and sent to the actor.
    If the actor feedback temperature changes (e.g. through mode change), the new target temperature is updated to the virtual temperature item.

    # KNX-things:
    Thing device heating_actor "KNX heating actor"{
        Type number : target_temperature    "Target Temperature"    [ ga="9.001:<3/6/11"]
        Type number : temperature_offset    "Temperature Offset"    [ ga="9.002:3/6/22" ]
    }

    # Items:
    Number:Temperature  target_temperature_OH   "Target Temperature"     <temperature>   ["Setpoint", "Temperature"]  {unit="°C", stateDescription=""[pattern="%.1f %unit%", min=5, max=27, step=0.5]}
    Number:Temperature  target_temperature_KNX  "Target Temperature KNX" <temperature>                                {channel="knx:device:bridge:heating_actor:target_temperature", unit="°C", stateDescription=""[pattern="%.1f %unit%"]}
    Number              temperature_offset      "Temperature Offset"     <temperature>                                {channel="knx:device:bridge:heating_actor:temperature_offset", stateDescription=""[pattern="%.1f °C", min=-5, max=5, step=0.5]}

    # Config:
    config = habapp_rules.actors.config.heating.KnxHeatingConfig(
            items=habapp_rules.actors.config.heating.KnxHeatingItems(
                    virtual_temperature="target_temperature_OH",
                    actor_feedback_temperature="target_temperature_KNX",
                    temperature_offset="temperature_offset"
    ))

    # Rule init:
    habapp_rules.actors.heating.KnxHeating(config)
    """

    def __init__(self, config: habapp_rules.actors.config.heating.KnxHeatingConfig) -> None:
        """Init of basic light object.

        Args:
            config: KNX heating config
        """
        HABApp.Rule.__init__(self)
        self._config = config

        self._temperature: float | None = config.items.actor_feedback_temperature.value
        if self._temperature is not None:
            config.items.virtual_temperature.oh_post_update(self._temperature)

        config.items.actor_feedback_temperature.listen_event(self._cb_actor_feedback_temperature_changed, HABApp.openhab.events.ItemStateChangedEventFilter())
        config.items.virtual_temperature.listen_event(self._cb_virtual_temperature_command, HABApp.openhab.events.ItemCommandEventFilter())

    def _cb_actor_feedback_temperature_changed(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the actor feedback temperature changed.

        Args:
            event: trigger event
        """
        self._config.items.virtual_temperature.oh_post_update(event.value)
        self._temperature = event.value

    def _cb_virtual_temperature_command(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
        """Callback, which is triggered if the virtual temperature received a command.

        Args:
            event: trigger event
        """
        if self._temperature is None:
            self._temperature = event.value

        if self._config.items.temperature_offset.value is None:
            self._config.items.temperature_offset.oh_send_command(0)

        # T_offset_new = T_target - T_base # noqa: ERA001
        # T_base = T_old - T_offset_old # noqa: ERA001
        # ==> T_offset_new = T_target - T_old + T_offset_old
        offset_new = event.value - self._temperature + self._config.items.temperature_offset.value
        self._config.items.temperature_offset.oh_send_command(offset_new)
        self._temperature = event.value


class HeatingActive(HABApp.Rule):
    """Rule sets a switch item to ON if any of the heating control values are above 0.

    # Items:
    Number      control_value_1         "Control Value 1"
    Number      control_value_2         "Control Value 2"
    Switch      heating_active          "Heating Active"

    # Config:
    config = habapp_rules.actors.config.heating.HeatingActiveConfig(
            items=habapp_rules.actors.config.heating.HeatingActiveItems(
                    control_values=["control_value_1", "control_value_2"]
                    output="heating_active"
    ))

    # Rule init:
    habapp_rules.actors.heating.HeatingActive(config)
    """

    def __init__(self, config: habapp_rules.actors.config.heating.HeatingActiveConfig) -> None:
        """Initialize the HeatingActive rule.

        Args:
            config: Config of the HeatingActive rule
        """
        HABApp.Rule.__init__(self)
        self._config = config

        self._extended_lock = self.run.countdown(self._config.parameter.extended_active_time, self._cb_lock_end)

        # callbacks
        self._config.items.output.listen_event(self._cb_output, HABApp.openhab.events.ItemStateChangedEventFilter())
        for itm in self._config.items.control_values:
            itm.listen_event(self._cb_control_value, HABApp.openhab.events.ItemStateChangedEventFilter())

        # reset extended lock if output is on
        if self._config.items.output.is_on():
            # start countdown if the output is already on
            self._extended_lock.reset()

        # set initial value
        elif self._config.items.output.value is None:
            ctr_values = [itm.value for itm in self._config.items.control_values if itm.value is not None]
            target_state = any(value > self._config.parameter.threshold for value in ctr_values) if ctr_values else False
            send_if_different(self._config.items.output, "ON" if target_state else "OFF")

    @staticmethod
    def _cb_output(event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if the output changed.

        Args:
            event: original trigger event
        """
        LOGGER.debug(f"Heating active output changed to {event.value}")

    def _cb_control_value(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if any of the control values changed.

        If the received value of the event or any of the other control values is above 0, it sets the output item to ON.
        Otherwise, it sets the output item to OFF.
        """
        if event.value > self._config.parameter.threshold or any(itm.value > self._config.parameter.threshold for itm in self._config.items.control_values if itm.value is not None):
            send_if_different(self._config.items.output, "ON")
            self._extended_lock.reset()
        elif not self._extended_lock.next_run_datetime:
            send_if_different(self._config.items.output, "OFF")

    def _cb_lock_end(self) -> None:
        """Callback function that is triggered when the extended lock period ends.

        Sets the output item to OFF if the lock period has expired.
        """
        send_if_different(self._config.items.output, "OFF")
