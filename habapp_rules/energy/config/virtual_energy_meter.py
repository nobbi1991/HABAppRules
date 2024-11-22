import dataclasses

import HABApp
import pydantic

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class EnergyMeterBaseItems(ItemBase): # todo add validation, that at least one item is set
	power_output: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="power output item, unit is W")
	energy_output: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="energy output item, unit is kWh")


class EnergyMeterSwitchItems(EnergyMeterBaseItems):
	monitored_switch: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="switch item, which will be monitored")


class EnergyMeterDimmerItems(EnergyMeterBaseItems):
	monitored_item: HABApp.openhab.items.DimmerItem | HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="dimmer / number item, which will be monitored")


class EnergyMeterSwitchParameter(ParameterBase):
	power: float = pydantic.Field(..., description="typical power in W if switch is ON", gt=0)


@dataclasses.dataclass
class Power:  # todo rename
	value: float  # todo rename
	power: float


class EnergyMeterDimmerParameter(EnergyMeterSwitchParameter):
	power: list[Power] = pydantic.Field(..., description="typical power if dimmed", min_length=2)


class EnergyMeterSwitchConfig(ConfigBase):
	items: EnergyMeterSwitchItems = pydantic.Field(..., description="items for the switch")
	parameter: EnergyMeterSwitchParameter = pydantic.Field(..., description="parameter for the switch")


class EnergyMeterDimmerConfig(ConfigBase):
	items: EnergyMeterDimmerItems = pydantic.Field(..., description="items for the dimmer")
	parameter: EnergyMeterDimmerParameter = pydantic.Field(..., description="parameter for the dimmer")
