"""Config models for KNX / MQTT bridge."""

import pydantic
import typing_extensions
from HABApp.openhab.items import DimmerItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class KnxMqttItems(ItemBase):
    """Configuration of items for KNX MQTT bridge."""

    mqtt_dimmer: DimmerItem = pydantic.Field(..., description="")
    knx_switch_ctr: SwitchItem | None = pydantic.Field(default=None, description="")
    knx_dimmer_ctr: DimmerItem | None = pydantic.Field(default=None, description="")

    @pydantic.model_validator(mode="after")
    def validate_knx_items(self) -> typing_extensions.Self:
        """Validate KNX items.

        Returns:
                validated model

        Raises:
                ValueError: if knx_switch_ctr and knx_dimmer_ctr are not set
        """
        if self.knx_switch_ctr is None and self.knx_dimmer_ctr is None:
            msg = "knx_switch_ctr or knx_dimmer_ctr must be set"
            raise ValueError(msg)
        return self

    @property
    def knx_item_name(self) -> str:
        """Get name of configured KNX item.

        Returns:
            name of configured KNX item
        """
        return self.knx_switch_ctr.name if self.knx_switch_ctr is not None else self.knx_dimmer_ctr.name  # type: ignore[union-attr]  # pydantic validator ensures that eather switch or dimmer is set


class KnxMqttParameter(ParameterBase):
    """Configuration of parameters for KNX MQTT bridge."""

    increase_value: int = pydantic.Field(default=60, description="")
    decrease_value: int = pydantic.Field(default=30, description="")


class KnxMqttConfig(ConfigBase):
    """Configuration of KNX MQTT bridge."""

    items: KnxMqttItems = pydantic.Field(..., description="Items for KNX MQTT bridge")
    parameter: KnxMqttParameter = pydantic.Field(KnxMqttParameter(), description="Parameters for KNX MQTT bridge")
