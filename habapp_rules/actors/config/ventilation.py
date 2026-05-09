"""Config models for ventilation rules."""

import datetime

import pydantic
from HABApp.openhab.items import NumberItem, StringItem, SwitchItem

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class StateConfig(pydantic.BaseModel):
    """Basic state config."""

    level: int
    display_text: str


class StateConfigWithTimeout(StateConfig):
    """State config with timeout."""

    timeout: int


class StateConfigLongAbsence(StateConfig):
    """State config for long absence state."""

    duration: int = 3600
    start_time: datetime.time = datetime.time(6)


class _VentilationItemsBase(ItemBase):
    """Base class for ventilation items."""

    manual: SwitchItem = pydantic.Field(..., description="Item to disable all automatic functions")
    hand_request: SwitchItem | None = pydantic.Field(None, description="Item to enter the hand state")
    external_request: SwitchItem | None = pydantic.Field(None, description="Item to enter the external state")
    presence_state: StringItem | None = pydantic.Field(None, description="Item of presence state to detect long absence")
    feedback_on: SwitchItem | None = pydantic.Field(None, description="Item which shows that ventilation is on")
    feedback_power: SwitchItem | None = pydantic.Field(None, description="Item which shows that ventilation is in power mode")
    display_text: StringItem | None = pydantic.Field(None, description="Item which can be used to set the display text")
    state: StringItem = pydantic.Field(..., description="Item for storing the current state")


class VentilationItems(_VentilationItemsBase):
    """Items for ventilation."""

    ventilation_level: NumberItem = pydantic.Field(..., description="Item to set the ventilation level")


class VentilationTwoStageItems(_VentilationItemsBase):
    """Items for ventilation."""

    ventilation_output_on: SwitchItem = pydantic.Field(..., description="Item to switch on the ventilation")
    ventilation_output_power: SwitchItem = pydantic.Field(..., description="Item to switch on the power mode")
    current: NumberItem | None = pydantic.Field(None, description="Item to measure the current of the ventilation")
    feedback_ventilation_level: NumberItem | None = pydantic.Field(None, description="Item feedback current ventilation level")


class VentilationParameter(ParameterBase):
    """Parameter for ventilation."""

    state_normal: StateConfig = pydantic.Field(default=StateConfig(level=1, display_text="Normal"))
    state_hand: StateConfigWithTimeout = pydantic.Field(default=StateConfigWithTimeout(level=2, display_text="Hand", timeout=3600))
    state_external: StateConfig = pydantic.Field(default=StateConfig(level=2, display_text="External"))
    state_humidity: StateConfig = pydantic.Field(default=StateConfig(level=2, display_text="Humidity"))
    state_long_absence: StateConfigLongAbsence = pydantic.Field(default=StateConfigLongAbsence(level=2, display_text="LongAbsence"))


class VentilationTwoStageParameter(VentilationParameter):
    """Parameter for ventilation."""

    state_after_run: StateConfig = pydantic.Field(default=StateConfig(level=2, display_text="After run"))
    after_run_timeout: int = pydantic.Field(default=390, description="")
    current_threshold_power: float = pydantic.Field(default=0.105, description="")


class VentilationConfig(ConfigBase):
    """Config for ventilation."""

    items: VentilationItems = pydantic.Field(..., description="Items for ventilation")
    parameter: VentilationParameter = pydantic.Field(VentilationParameter(), description="Parameter for ventilation")


class VentilationTwoStageConfig(ConfigBase):
    """Config for ventilation."""

    items: VentilationTwoStageItems = pydantic.Field(..., description="Items for ventilation")
    parameter: VentilationTwoStageParameter = pydantic.Field(VentilationTwoStageParameter(), description="Parameter for ventilation")
