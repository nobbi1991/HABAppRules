"""Config models for shading rules."""

from __future__ import annotations

import copy

import HABApp.openhab.items  # noqa: TC002
import pydantic
import typing_extensions

import habapp_rules.core.pydantic_base


class ShadingPosition(pydantic.BaseModel):
    """Position of shading object."""

    position: float | bool | None = pydantic.Field(..., description="target position")
    slat: float | None = pydantic.Field(None, description="target slat position")

    def __init__(self, position: float | bool | None, slat: float | None = None) -> None:
        """Initialize shading position with position and slat.

        Args:
            position: target position value
            slat: slat value
        """
        super().__init__(position=position, slat=slat)


class ShadingItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for shading rules."""

    shading_position: HABApp.openhab.items.RollershutterItem | HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="item for setting the shading position")
    slat: HABApp.openhab.items.DimmerItem | None = pydantic.Field(None, description="item for setting the slat value")
    manual: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item to switch to manual mode and disable the automatic functions")
    shading_position_control: list[HABApp.openhab.items.RollershutterItem | HABApp.openhab.items.DimmerItem] = pydantic.Field([], description="control items to improve manual detection")
    shading_position_group: list[HABApp.openhab.items.RollershutterItem | HABApp.openhab.items.DimmerItem] = pydantic.Field([], description="")
    wind_alarm: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="item which is ON when wind alarm is active")
    sun_protection: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="item which is ON when sun protection is needed")
    sun_protection_slat: HABApp.openhab.items.DimmerItem | None = pydantic.Field(None, description="value for the slat when sun protection is active")
    sleeping_state: HABApp.openhab.items.StringItem | None = pydantic.Field(None, description="item of the sleeping state set via habapp_rules.system.sleep.Sleep")
    night: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="item which is ON at night or darkness")
    door: HABApp.openhab.items.ContactItem | None = pydantic.Field(None, description="item for setting position when door is opened")
    summer: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="item which is ON during summer")
    hand_manual_is_active_feedback: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="feedback item which is ON when hand or manual is active")
    state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item to store the current state of the state machine")


class ShadingParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for shading rules."""

    pos_auto_open: ShadingPosition = pydantic.Field(ShadingPosition(0, 0), description="position for auto open")
    pos_wind_alarm: ShadingPosition | None = pydantic.Field(ShadingPosition(0, 0), description="position for wind alarm")
    pos_sleeping_night: ShadingPosition | None = pydantic.Field(ShadingPosition(100, 100), description="position for sleeping at night")
    pos_sleeping_day: ShadingPosition | None = pydantic.Field(None, description="position for sleeping at day")
    pos_sun_protection: ShadingPosition | None = pydantic.Field(ShadingPosition(100, None), description="position for sun protection")
    pos_night_close_summer: ShadingPosition | None = pydantic.Field(None, description="position for night close during summer")
    pos_night_close_winter: ShadingPosition | None = pydantic.Field(ShadingPosition(100, 100), description="position for night close during winter")
    pos_door_open: ShadingPosition | None = pydantic.Field(ShadingPosition(0, 0), description="position if door is opened")
    manual_timeout: int = pydantic.Field(24 * 3600, description="fallback timeout for manual state", gt=0)
    door_post_time: int = pydantic.Field(5 * 60, description="extended time after door is closed", gt=0)
    value_tolerance: int = pydantic.Field(0, description="value tolerance for shading position which is allowed without manual detection", ge=0)

    @pydantic.model_validator(mode="after")
    def validate_model(self) -> typing_extensions.Self:
        """Validate model.

        Returns:
            validated model
        """
        if self.pos_sleeping_night and not self.pos_sleeping_day:
            self.pos_sleeping_day = copy.deepcopy(self.pos_sleeping_night)
        return self


class ShadingConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for shading objects."""

    items: ShadingItems = pydantic.Field(..., description="items for shading")
    parameter: ShadingParameter = pydantic.Field(ShadingParameter(), description="parameter for shading")

    @pydantic.model_validator(mode="after")
    def validate_model(self) -> typing_extensions.Self:
        """Validate model.

        Returns:
            validated model

        Raises:
            AssertionError: if 'parameter.pos_night_close_summer' is set but 'items.summer' is missing
        """
        if self.parameter.pos_night_close_summer is not None and self.items.summer is None:
            msg = "Night close position is set for summer, but item for summer / winter is missing!"
            raise AssertionError(msg)
        return self


class ResetAllManualHandItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for reset all manual hand items."""

    reset_manual_hand: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item for resetting manual and hand state to automatic state")


class ResetAllManualHandParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for reset all manual hand parameter."""

    shading_objects: list[object] | None = pydantic.Field(None, description="list of shading objects to reset")


class ResetAllManualHandConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for reset all manual hand config."""

    items: ResetAllManualHandItems = pydantic.Field(..., description="items for reset all manual hand config")
    parameter: ResetAllManualHandParameter = pydantic.Field(ResetAllManualHandParameter(), description="parameter for reset all manual hand config")


class SlatValueItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for slat values for sun protection."""

    sun_elevation: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="item for sun elevation")
    slat_value: HABApp.openhab.items.NumberItem | HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="item for slat value, which should be set")
    summer: HABApp.openhab.items.SwitchItem | None = pydantic.Field(None, description="item for summer")


class ElevationSlatMapping(pydantic.BaseModel):
    """Mapping from elevation to slat value."""

    elevation: int
    slat_value: int

    def __init__(self, elevation: int, slat_value: int) -> None:
        """Initialize the elevation slat mapping.

        Args:
            elevation: elevation value
            slat_value: mapped slat value
        """
        super().__init__(elevation=elevation, slat_value=slat_value)


class SlatValueParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for slat values for sun protection."""

    elevation_slat_characteristic: list[ElevationSlatMapping] = pydantic.Field(
        [ElevationSlatMapping(0, 100), ElevationSlatMapping(4, 100), ElevationSlatMapping(8, 90), ElevationSlatMapping(18, 80), ElevationSlatMapping(26, 70), ElevationSlatMapping(34, 60), ElevationSlatMapping(41, 50)],
        description="list of tuple-mappings from elevation to slat value",
    )
    elevation_slat_characteristic_summer: list[ElevationSlatMapping] = pydantic.Field(
        [ElevationSlatMapping(0, 100), ElevationSlatMapping(4, 100), ElevationSlatMapping(8, 90), ElevationSlatMapping(18, 80)], description="list of tuple-mappings from elevation to slat value, which is used if summer is active"
    )

    @pydantic.field_validator("elevation_slat_characteristic", "elevation_slat_characteristic_summer")
    @classmethod
    def sort_mapping(cls, values: list[ElevationSlatMapping]) -> list[ElevationSlatMapping]:
        """Sort the elevation slat mappings.

        Args:
            values: input values

        Returns:
            sorted values

        Raises:
            AssertionError: if elevation values are not unique
        """
        values.sort(key=lambda x: x.elevation)

        if len(values) != len({value.elevation for value in values}):
            msg = "Elevation values must be unique!"
            raise AssertionError(msg)

        return values


class SlatValueConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for slat values for sun protection."""

    items: SlatValueItems = pydantic.Field(..., description="items for slat values for sun protection")
    parameter: SlatValueParameter = pydantic.Field(SlatValueParameter(), description="parameter for slat values for sun protection")


class ReferenceRunItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for reference run."""

    trigger_run: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item for triggering the reference run")
    last_run: HABApp.openhab.items.DatetimeItem = pydantic.Field(..., description="item for date/time of the last run")
    presence_state: HABApp.openhab.items.StringItem = pydantic.Field(..., description="item for presence state")


class ReferenceRunConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for reference run."""

    items: ReferenceRunItems = pydantic.Field(..., description="items for reference run")
    parameter: None = None
