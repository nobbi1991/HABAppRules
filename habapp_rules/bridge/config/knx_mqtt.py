"""Config models for KNX / MQTT bridge."""

import HABApp.openhab.items
import pydantic
import typing_extensions

import habapp_rules.core.pydantic_base


class KnxMqttItems(habapp_rules.core.pydantic_base.ItemBase):
    """Configuration of items for KNX MQTT bridge."""

    mqtt_dimmer: HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="")
    knx_switch_ctr: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="")
    knx_dimmer_ctr: HABApp.openhab.items.DimmerItem | None = pydantic.Field(None, description="")

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


class KnxMqttParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Configuration of parameters for KNX MQTT bridge."""

    increase_value: int = pydantic.Field(60, description="")
    decrease_value: int = pydantic.Field(30, description="")


class KnxMqttConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Configuration of KNX MQTT bridge."""

    items: KnxMqttItems = pydantic.Field(..., description="Items for KNX MQTT bridge")
    parameter: KnxMqttParameter = pydantic.Field(KnxMqttParameter(), description="Parameters for KNX MQTT bridge")
