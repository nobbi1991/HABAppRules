import logging

import HABApp
from wakeonlan import send_magic_packet

import habapp_rules.network.config.wol

LOGGER = logging.getLogger(__name__)


class Wol(HABApp.Rule):
    """Rule for wake up a device via WOL.

    Use habapp_rules.network.config.wol.WolConfig to configure this rule.
    """

    def __init__(self, config: habapp_rules.network.config.wol.WolConfig) -> None:
        """Init Rule.

        Args:
            config: config for WOL rule
        """
        HABApp.Rule.__init__(self)
        self._config = config
        self._config.items.trigger_wol.listen_event(self._cb_trigger_wol, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _cb_trigger_wol(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if the trigger_wol item changed.

        Args:
            event: event which triggered this callback

        """
        if event.value == "ON":
            send_magic_packet(self._config.parameter.mac_address)
            LOGGER.info(f"Triggered WOL for '{self._config.parameter.log_name}'")
            self._config.items.trigger_wol.oh_send_command("OFF")
