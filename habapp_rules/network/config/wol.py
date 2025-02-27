import HABApp
import pydantic
from pydantic_extra_types.mac_address import MacAddress

import habapp_rules.core.pydantic_base


class WolItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for WOL rule."""

    trigger_wol: HABApp.openhab.items.switch_item.SwitchItem = pydantic.Field(..., description="item which triggers the WOL")


class WolParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for WOL rule."""

    mac_address: MacAddress = pydantic.Field(..., description="MAC address of the device to wake up")
    friendly_name: str | None = pydantic.Field(None, description="Name which is used for logging")

    @property
    def log_name(self) -> str:
        """Get name for logging.

        Returns:
            Name which is can be used for logging
        """
        return self.friendly_name or self.mac_address


class WolConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for WOL rule."""

    items: WolItems = pydantic.Field(..., description="items for WOL")
    parameter: WolParameter = pydantic.Field(..., description="parameter for WOL")
