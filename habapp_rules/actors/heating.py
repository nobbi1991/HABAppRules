"""Heating rules."""

import HABApp

import habapp_rules.actors.config.heating


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
