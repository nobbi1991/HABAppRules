"""Config models for ventilation rules."""

import datetime

import HABApp
import pydantic

import habapp_rules.core.pydantic_base


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


class _VentilationItemsBase(habapp_rules.core.pydantic_base.ItemBase):
    """Base class for ventilation items."""

    manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="Item to disable all automatic functions")
    hand_request: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="Item to enter the hand state")
    external_request: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="Item to enter the external state")
    presence_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="Item of presence state to detect long absence")
    feedback_on: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="Item which shows that ventilation is on")
    feedback_power: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="Item which shows that ventilation is in power mode")
    display_text: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="Item which can be used to set the display text")
    state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="Item for storing the current state")


class VentilationItems(_VentilationItemsBase):
    """Items for ventilation."""

    ventilation_level: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="Item to set the ventilation level")


class VentilationTwoStageItems(_VentilationItemsBase):
    """Items for ventilation."""

    ventilation_output_on: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="Item to switch on the ventilation")
    ventilation_output_power: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="Item to switch on the power mode")
    current: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="Item to measure the current of the ventilation")
    feedback_ventilation_level: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="Item feedback current ventilation level")


class VentilationParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for ventilation."""

    state_normal: StateConfig = pydantic.Field(StateConfig(level=1, display_text="Normal"))
    state_hand: StateConfigWithTimeout = pydantic.Field(StateConfigWithTimeout(level=2, display_text="Hand", timeout=3600))
    state_external: StateConfig = pydantic.Field(StateConfig(level=2, display_text="External"))
    state_humidity: StateConfig = pydantic.Field(StateConfig(level=2, display_text="Humidity"))
    state_long_absence: StateConfigLongAbsence = pydantic.Field(StateConfigLongAbsence(level=2, display_text="LongAbsence"))


class VentilationTwoStageParameter(VentilationParameter):
    """Parameter for ventilation."""

    state_after_run: StateConfig = pydantic.Field(StateConfig(level=2, display_text="After run"))
    after_run_timeout: int = pydantic.Field(390, description="")
    current_threshold_power: float = pydantic.Field(0.105, description="")


class VentilationConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for ventilation."""

    items: VentilationItems = pydantic.Field(..., description="Items for ventilation")
    parameter: VentilationParameter = pydantic.Field(VentilationParameter(), description="Parameter for ventilation")


class VentilationTwoStageConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for ventilation."""

    items: VentilationTwoStageItems = pydantic.Field(..., description="Items for ventilation")
    parameter: VentilationTwoStageParameter = pydantic.Field(VentilationTwoStageParameter(), description="Parameter for ventilation")
