import pydantic
from HABApp.openhab.items import DimmerItem, NumberItem, StringItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class BathroomLightItems(ItemBase):
    """Items for bathroom light."""

    # lights
    light_main: DimmerItem = pydantic.Field(..., description="main light item")
    light_main_ctr: DimmerItem | None = pydantic.Field(None, description="control item for main light, this can be used to detect switch on via dimming")
    light_main_color: NumberItem = pydantic.Field(..., description="main light color (Kelvin)")
    light_main_hcl: SwitchItem = pydantic.Field(..., description="set HCL mode from KNX actor active for main light")
    light_mirror: DimmerItem = pydantic.Field(..., description="mirror light item")

    # environment
    sleeping_state: StringItem = pydantic.Field(..., description="sleeping state item")
    presence_state: StringItem = pydantic.Field(..., description="presence state item")

    # state machine
    manual: SwitchItem = pydantic.Field(..., description="item to switch to manual mode and disable the automatic functions")
    state: StringItem = pydantic.Field(..., description="item to store the current state of the state machine")


class BathroomLightParameter(ParameterBase):
    """Parameter for bathroom light."""

    color_mirror_sync: float = pydantic.Field(default=4000, description="color temperature for the mirror")
    min_brightness_mirror_sync: int = pydantic.Field(default=80, description="minimum brightness for main light if main and mirror light is ON")
    color_night: int = pydantic.Field(default=2600, description="color temperature for night mode")
    brightness_night: int = pydantic.Field(default=40, description="brightness for night mode")
    extended_sleep_time: int = pydantic.Field(default=15 * 60, description="additional sleep time in seconds", gt=0)
    brightness_night_extended: int | None = pydantic.Field(default=None, description="brightness for night mode extended")


class BathroomLightConfig(ConfigBase):
    """Config for bathroom light."""

    items: BathroomLightItems = pydantic.Field(..., description="items for the switch")
    parameter: BathroomLightParameter = pydantic.Field(BathroomLightParameter(), description="parameter for the switch")
