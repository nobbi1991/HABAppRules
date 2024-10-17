"""Config models for heating rules."""
import HABApp.openhab.items
import pydantic

import habapp_rules.core.pydantic_base


class KnxHeatingItems(habapp_rules.core.pydantic_base.ItemBase):
	"""Items for KNX heating abstraction rule."""
	virtual_temperature: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="temperature item, which is used in OpenHAB to set the target temperature")
	actor_feedback_temperature: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="temperature item, which holds the current target temperature set by the heating actor")
	temperature_offset: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="item for setting the offset temperature")


class KnxHeatingConfig(habapp_rules.core.pydantic_base.ConfigBase):
	"""Config for KNX heating abstraction rule."""
	items: KnxHeatingItems = pydantic.Field(..., description="items for heating rule")
	parameter: None = None
