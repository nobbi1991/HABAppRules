"""Rules for bridging KNX controller to MQTT items."""

import logging

import HABApp

import habapp_rules.bridge.config.knx_mqtt
import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class KnxMqttDimmerBridge(HABApp.Rule):
    """Create a bridge to control a MQTT dimmer from a KNX controller (e.g. wall switch).

    To use this the items must be configured according the following example:
    - mqtt_dimmer: autoupdate should be false, thing: according to OpenHAB documentation
    - knx_switch_ctr: autoupdate must be activated, thing:  [ ga="1/1/124+1/1/120" ] for ga: at first always use the RM-GA, second is the control-GA
    - knx_dimmer_ctr: autoupdate must be activated, thing:  [ position="1/1/125+1/1/123", increaseDecrease="1/1/122" ] for position: at first always use the RM-GA, second is the control-GA

    info: OpenHAB does not support start/stop dimming. Thus, this implementation will set fixed values if INCREASE/DECREASE was received from KNX
    """

    def __init__(self, config: habapp_rules.bridge.config.knx_mqtt.KnxMqttConfig) -> None:
        """Create object of KNX to MQTT bridge.

        Args:
            config: Configuration of the KNX MQTT bridge

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationException: If config is not valid
        """
        self._config = config
        knx_name = self._config.items.knx_switch_ctr.name if self._config.items.knx_switch_ctr is not None else self._config.items.knx_dimmer_ctr.name

        HABApp.Rule.__init__(self)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, f"{knx_name}__{self._config.items.mqtt_dimmer.name}")

        self._config.items.mqtt_dimmer.listen_event(self._cb_mqtt_event, HABApp.openhab.events.ItemStateChangedEventFilter())
        if self._config.items.knx_dimmer_ctr is not None:
            self._config.items.knx_dimmer_ctr.listen_event(self._cb_knx_event, HABApp.openhab.events.ItemCommandEventFilter())
        if self._config.items.knx_switch_ctr is not None:
            self._config.items.knx_switch_ctr.listen_event(self._cb_knx_event, HABApp.openhab.events.ItemCommandEventFilter())
        self._instance_logger.debug("successful!")

    def _cb_knx_event(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
        """Callback, which is called if a KNX command received.

        Args:
            event: HABApp event
        """
        if isinstance(event.value, int | float) or event.value in {"ON", "OFF"}:
            self._config.items.mqtt_dimmer.oh_send_command(event.value)
        elif event.value == "INCREASE":
            target_value = self._config.parameter.increase_value if self._config.items.mqtt_dimmer.value < self._config.parameter.increase_value else 100
            self._config.items.mqtt_dimmer.oh_send_command(target_value)
        elif event.value == "DECREASE":
            target_value = self._config.parameter.decrease_value if self._config.items.mqtt_dimmer.value > self._config.parameter.decrease_value else 0
            self._config.items.mqtt_dimmer.oh_send_command(target_value)
        else:
            self._instance_logger.error(f"command '{event.value}' ist not supported!")

    def _cb_mqtt_event(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if a MQTT state change event happens.

        Args:
            event: HABApp event
        """
        if not isinstance(event.value, int | float):
            return

        if self._config.items.knx_dimmer_ctr is not None:
            self._config.items.knx_dimmer_ctr.oh_post_update(event.value)

        if self._config.items.knx_switch_ctr is not None:
            self._config.items.knx_switch_ctr.oh_post_update("ON" if event.value > 0 else "OFF")
