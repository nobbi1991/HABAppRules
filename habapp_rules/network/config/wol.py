import pydantic
from HABApp.openhab.items import SwitchItem
from pydantic_extra_types.mac_address import MacAddress

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class WolItems(ItemBase):
    """Items for WOL rule."""

    trigger_wol: SwitchItem = pydantic.Field(..., description="item which triggers the WOL")


class WolParameter(ParameterBase):
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


class WolConfig(ConfigBase):
    """Config for WOL rule."""

    items: WolItems = pydantic.Field(..., description="items for WOL")
    parameter: WolParameter = pydantic.Field(..., description="parameter for WOL")
