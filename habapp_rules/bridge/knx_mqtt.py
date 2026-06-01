"""Rules for bridging KNX controller to MQTT items."""

from HABApp.openhab.events import ItemCommandEvent, ItemStateChangedEvent
from HABApp.openhab.events.event_filters import ItemCommandEventFilter, ItemStateChangedEventFilter

from habapp_rules.bridge.config.knx_mqtt import KnxMqttConfig
from habapp_rules.core.base import RuleBase


class KnxMqttDimmerBridge(RuleBase):
    """Create a bridge to control a MQTT dimmer from a KNX controller (e.g. wall switch).

    To use this the items must be configured according the following example:
    - mqtt_dimmer: autoupdate should be false, thing: according to OpenHAB documentation
    - knx_switch_ctr: autoupdate must be activated, thing:  [ ga="1/1/124+1/1/120" ] for ga: at first always use the RM-GA, second is the control-GA
    - knx_dimmer_ctr: autoupdate must be activated, thing:  [ position="1/1/125+1/1/123", increaseDecrease="1/1/122" ] for position: at first always use the RM-GA, second is the control-GA

    info: OpenHAB does not support start/stop dimming. Thus, this implementation will set fixed values if INCREASE/DECREASE was received from KNX
    """

    def __init__(self, config: KnxMqttConfig) -> None:
        """Create object of KNX to MQTT bridge.

        Args:
            config: Configuration of the KNX MQTT bridge

        Raises:
            HabAppRulesConfigurationException: If config is not valid
        """
        self._config = config
        knx_name = self._config.items.knx_item_name

        RuleBase.__init__(self, f"{knx_name}__{self._config.items.mqtt_dimmer.name}")

        self._config.items.mqtt_dimmer.listen_event(self._cb_mqtt_event, ItemStateChangedEventFilter())
        if self._config.items.knx_dimmer_ctr is not None:
            self._config.items.knx_dimmer_ctr.listen_event(self._cb_knx_event, ItemCommandEventFilter())
        if self._config.items.knx_switch_ctr is not None:
            self._config.items.knx_switch_ctr.listen_event(self._cb_knx_event, ItemCommandEventFilter())
        self._log_init_done()

    def _cb_knx_event(self, event: ItemCommandEvent) -> None:
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

    def _cb_mqtt_event(self, event: ItemStateChangedEvent) -> None:
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
