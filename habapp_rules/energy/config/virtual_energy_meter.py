import HABApp
import pydantic
import typing_extensions
from pydantic import model_validator

from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class EnergyMeterBaseItems(ItemBase):
    """Base class for energy meter items."""

    power_output: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="power output item, unit is W")
    energy_output: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="energy output item, unit is kWh")

    @pydantic.model_validator(mode="after")
    def validate_items(self) -> typing_extensions.Self:
        """Validate items.

        Returns:
            Validated items

        Raises:
            HabAppRulesConfigurationError: if items are not valid
        """
        if self.power_output is None and self.energy_output is None:
            msg = "At least one of power_output or energy_output must be set"
            raise HabAppRulesConfigurationError(msg)
        return self


class EnergyMeterSwitchItems(EnergyMeterBaseItems):
    """Items for virtual energy meter for a switch item."""

    monitored_switch: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="switch item, which will be monitored")


class EnergyMeterNumberItems(EnergyMeterBaseItems):
    """Items for virtual energy meter for a dimmer item."""

    monitored_item: HABApp.openhab.items.DimmerItem | HABApp.openhab.items.NumberItem = pydantic.Field(..., description="dimmer item, which will be monitored")


class EnergyMeterBaseParameter(ParameterBase):
    """Base class for energy meter parameters."""

    energy_update_resolution: int = pydantic.Field(0.010, description="update the energy item every x kWh. Default is 0.01kWh == 10 Wh", gt=0)


class EnergyMeterSwitchParameter(EnergyMeterBaseParameter):
    """Parameter for a virtual energy meter for a switch item."""

    power: float = pydantic.Field(..., description="typical power in W if switch is ON", gt=0)


class PowerMapping(pydantic.BaseModel):
    """Class to map a value to a power.

    This can be used to map e.g. a dimmer value to used power
    """

    value: float = pydantic.Field(..., description="dimmer / number value, which will be mapped to a power value")
    power: float = pydantic.Field(..., description="power in W")

    def __init__(self, value: float, power: float) -> None:
        """Init PowerMapping.

        Args:
            value: dimmer / number value
            power: power in W
        """
        super().__init__(value=value, power=power)


class EnergyMeterNumberParameter(EnergyMeterBaseParameter):
    """Parameter for a virtual energy meter for a dimmer item."""

    power_mapping: list[PowerMapping] = pydantic.Field(..., description="typical power if dimmed")

    @pydantic.field_validator("power_mapping")
    @classmethod
    def validate_power_mapping(cls, mappings: list[PowerMapping]) -> list[PowerMapping]:
        """Validate power_mapping.

        Args:
            mappings: list of power mappings

        Returns:
            Validated list of power mappings

        Raises:
            HabAppRulesConfigurationError: if power_mapping is not valid
        """
        if len(mappings) < 2:  # noqa: PLR2004
            msg = "power_mapping must have at least 2 elements"
            raise HabAppRulesConfigurationError(msg)

        mappings.sort(key=lambda x: x.value)
        return mappings

    def get_power(self, dimmer_value: float) -> float:
        """Get power depending on dimmer value.

        Args:
            dimmer_value: value of the dimmer

        Returns:
            power depending on dimmer value
        """
        idx = next((i for i, mapping in enumerate(self.power_mapping) if mapping.value >= dimmer_value), None)

        if idx is None:
            # If no such index is found, return the power of the last mapping
            return self.power_mapping[-1].power

        if idx == 0:
            # If the input value is less than the first mapping, return the power of the first mapping
            return self.power_mapping[0].power

        # Otherwise, interpolate the power between the two surrounding mappings
        prev_mapping = self.power_mapping[idx - 1]
        return prev_mapping.power + (self.power_mapping[idx].power - prev_mapping.power) * (dimmer_value - prev_mapping.value) / (self.power_mapping[idx].value - prev_mapping.value)


class EnergyMeterSwitchConfig(ConfigBase):
    """Config for virtual energy meter for a switch item."""

    items: EnergyMeterSwitchItems = pydantic.Field(..., description="items for the switch")
    parameter: EnergyMeterSwitchParameter = pydantic.Field(..., description="parameter for the switch")


class EnergyMeterNumberConfig(ConfigBase):
    """Config for virtual energy meter for a dimmer item."""

    items: EnergyMeterNumberItems = pydantic.Field(..., description="items for the dimmer")
    parameter: EnergyMeterNumberParameter = pydantic.Field(..., description="parameter for the dimmer")

    @model_validator(mode="after")
    def validate_model(self) -> typing_extensions.Self:
        """Validate model.

        Returns:
            Validated model

        Raises:
            HabAppRulesConfigurationError: if config is not valid
        """
        if isinstance(self.items.monitored_item, HABApp.openhab.items.DimmerItem):
            all_values = [mapping.value for mapping in self.parameter.power_mapping]
            if any(value < 0 for value in all_values) or any(value > 100 for value in all_values):  # noqa: PLR2004
                msg = "power_mapping values for dimmer items must be between 0 and 100"
                raise HabAppRulesConfigurationError(msg)
        return self
