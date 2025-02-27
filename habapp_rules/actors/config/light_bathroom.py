import HABApp
import pydantic

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class BathroomLightItems(ItemBase):
    """Items for bathroom light."""

    # lights
    light_main: HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="main light item")
    light_main_ctr: HABApp.openhab.items.DimmerItem | None = pydantic.Field(None, description="control item for main light, this can be used to detect switch on via dimming")
    light_main_color: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="main light color (Kelvin)")
    light_main_hcl: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="set HCL mode from KNX actor active for main light")
    light_mirror: HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="mirror light item")

    # environment
    sleeping_state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="sleeping state item")
    presence_state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="presence state item")

    # state machine
    manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item to switch to manual mode and disable the automatic functions")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item to store the current state of the state machine")


class BathroomLightParameter(ParameterBase):
    """Parameter for bathroom light."""

    color_mirror_sync: float = pydantic.Field(4000, description="color temperature for the mirror")
    min_brightness_mirror_sync: int = pydantic.Field(80, description="minimum brightness for main light if main and mirror light is ON")
    color_night: int = pydantic.Field(2600, description="color temperature for night mode")
    brightness_night: int = pydantic.Field(40, description="brightness for night mode")
    extended_sleep_time: int = pydantic.Field(15 * 60, description="additional sleep time in seconds", gt=0)
    brightness_night_extended: int | None = pydantic.Field(None, description="brightness for night mode extended")


class BathroomLightConfig(ConfigBase):
    """Config for bathroom light."""

    items: BathroomLightItems = pydantic.Field(..., description="items for the switch")
    parameter: BathroomLightParameter = pydantic.Field(BathroomLightParameter(), description="parameter for the switch")
