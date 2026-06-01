from HABApp.openhab.events import ItemStateChangedEvent
from HABApp.openhab.events.event_filters import ItemStateChangedEventFilter
from wakeonlan import send_magic_packet

from habapp_rules.core.base import RuleBase
from habapp_rules.network.config.wol import WolConfig


class Wol(RuleBase):
    """Rule for wake up a device via WOL.

    Use WolConfig to configure this rule.
    """

    def __init__(self, config: WolConfig) -> None:
        """Init Rule.

        Args:
            config: config for WOL rule
        """
        RuleBase.__init__(self, config.items.trigger_wol.name)
        self._config = config
        self._config.items.trigger_wol.listen_event(self._cb_trigger_wol, ItemStateChangedEventFilter())
        self._log_init_done()

    def _cb_trigger_wol(self, event: ItemStateChangedEvent) -> None:
        """Callback which is triggered if the trigger_wol item changed.

        Args:
            event: event which triggered this callback

        """
        if event.value == "ON":
            send_magic_packet(self._config.parameter.mac_address)
            self._instance_logger.info(f"Triggered WOL for '{self._config.parameter.log_name}'")
            self._config.items.trigger_wol.oh_send_command("OFF")
