import HABApp.openhab.items.switch_item
import pydantic

import habapp_rules.core.pydantic_base


class LowBatteryItems(habapp_rules.core.pydantic_base.ItemBase):
    warning_low_battery: HABApp.openhab.items.switch_item.SwitchItem = pydantic.Field(..., description="item which is ON if at least one battery is low")
    low_battery_group: HABApp.openhab.items.group_item.GroupItem = pydantic.Field(..., description="group which contains all low battery items")  # TODO change text


class LowBatteryParameter(habapp_rules.core.pydantic_base.ParameterBase):
    update_items_time: int = pydantic.Field(3 * 24 * 3600, description="time in seconds to update items", gt=0)  # default: update items every 3 days
    check_values_time: int = pydantic.Field(24 * 3600, description="time in seconds to check values", gt=0)  # default: check values every day
    low_battery_threshold: float = pydantic.Field(20, description="threshold in percent", gt=0)


class LowBatteryConfig(habapp_rules.core.pydantic_base.ConfigBase):
    items: LowBatteryItems = pydantic.Field(..., description="items for low battery")
    parameter: LowBatteryParameter = pydantic.Field(LowBatteryParameter(), description="parameter for low battery")
