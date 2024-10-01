"""Config models for power rules rules."""

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


class CurrentSwitchItems(habapp_rules.core.pydantic_base.ItemBase):
	"""Items for current switch the rule."""

	current: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="item which measures the current")
	switch: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which should be switched on, if the current is above")


class CurrentSwitchParameter(habapp_rules.core.pydantic_base.ParameterBase):
	"""Parameter for current switch the rules."""

	threshold: float = pydantic.Field(200, description="threshold for switching on")


class CurrentSwitchConfig(habapp_rules.core.pydantic_base.ConfigBase):
	"""Config models for current switch the rule."""

	items: CurrentSwitchItems = pydantic.Field(..., description="items for current switch rules")
	parameter: CurrentSwitchParameter = pydantic.Field(CurrentSwitchParameter(), description="parameter for current switch rules")
