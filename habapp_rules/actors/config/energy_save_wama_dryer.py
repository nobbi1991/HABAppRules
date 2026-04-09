import HABApp
import pydantic

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class EnergySaveWaMaDryerItems(ItemBase):
    """Items for washing machine / dryer energy save rule."""

    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item to store the current state of the state machine")
    manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which disables all automatic actions")
    external_request: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which triggers the external request")
    wama_delayed_start: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which holds the state, if the washing machine will start delayed")

    wama_switch: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which switches the washing machine")
    wama_current: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="item which measures the current of the washing machine")

    dryer_switch: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which switches the dryer")
    dryer_current: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="item which measures the current of the dryer")


class EnergySaveWaMaDryerParameter(ParameterBase):
    """Parameter for washing machine / dryer energy save rule."""

    wama_current_threshold: float = pydantic.Field(..., description="threshold for the current of the washing machine")
    wama_extended_wait_for_current_time: int = pydantic.Field(2 * 3600, description="Extended time to wait time before switch off the washing machine relay in seconds. If current goes above threshold, it will jump back to ON state.", gt=0)
    wama_hand_timeout: int | None = pydantic.Field(3 * 3600, description="Fallback time from hand to automatic mode in seconds. None means no timeout.")

    dryer_current_threshold: float = pydantic.Field(..., description="threshold for the current of the washing machine")
    dryer_extended_wait_for_current_time: int = pydantic.Field(4 * 3600, description="Extended time to wait time before switch off the washing machine relay in seconds. If current goes above threshold, it will jump back to ON state.", gt=0)
    dryer_hand_timeout: int | None = pydantic.Field(3 * 3600, description="Fallback time from hand to automatic mode in seconds. None means no timeout.")


class EnergySaveWaMaDryerConfig(ConfigBase):
    """Config for washing machine / dryer energy save rule."""

    items: EnergySaveWaMaDryerItems = pydantic.Field(..., description="Items for power switch rule")
    parameter: EnergySaveWaMaDryerParameter = pydantic.Field(..., description="Parameter for power switch rule")
