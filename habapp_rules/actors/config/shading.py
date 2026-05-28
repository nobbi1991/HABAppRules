"""Config models for shading rules."""

from __future__ import annotations

import copy
from typing import Any

import pydantic
import typing_extensions
from HABApp.openhab.items import ContactItem, DatetimeItem, DimmerItem, NumberItem, RollershutterItem, StringItem, SwitchItem  # noqa: TC002

from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class ShadingPosition(pydantic.BaseModel):
    """Position of shading object."""

    position: float | bool | None = pydantic.Field(..., description="target position")
    slat: float | None = pydantic.Field(default=None, description="target slat position")

    def __init__(self, position: float | bool | None, slat: float | None = None) -> None:
        """Initialize shading position with position and slat.

        Args:
            position: target position value
            slat: slat value
        """
        super().__init__(position=position, slat=slat)


class ShadingItems(ItemBase):
    """Items for shading rules."""

    shading_position: RollershutterItem | DimmerItem = pydantic.Field(..., description="item for setting the shading position")
    slat: DimmerItem | None = pydantic.Field(default=None, description="item for setting the slat value")
    manual: SwitchItem = pydantic.Field(..., description="item to switch to manual mode and disable the automatic functions")
    shading_position_control: list[RollershutterItem | DimmerItem] = pydantic.Field(default=[], description="control items to improve manual detection")
    shading_position_group: list[RollershutterItem | DimmerItem] = pydantic.Field(default=[], description="")
    wind_alarm: SwitchItem | None = pydantic.Field(default=None, description="item which is ON when wind alarm is active")
    sun_protection: SwitchItem | None = pydantic.Field(default=None, description="item which is ON when sun protection is needed")
    sun_protection_slat: DimmerItem | None = pydantic.Field(default=None, description="value for the slat when sun protection is active")
    sleeping_state: StringItem | None = pydantic.Field(default=None, description="item of the sleeping state set via habapp_rules.system.sleep.Sleep")
    night: SwitchItem | None = pydantic.Field(default=None, description="item which is ON at night or darkness")
    door: ContactItem | None = pydantic.Field(default=None, description="item for setting position when door is opened")
    summer: SwitchItem | None = pydantic.Field(default=None, description="item which is ON during summer")
    hand_manual_is_active_feedback: SwitchItem | None = pydantic.Field(default=None, description="feedback item which is ON when hand or manual is active")
    state: StringItem = pydantic.Field(..., description="item to store the current state of the state machine")


class ShadingParameter(ParameterBase):
    """Parameter for shading rules."""

    pos_auto_open: ShadingPosition = pydantic.Field(default=ShadingPosition(0, 0), description="position for auto open")
    pos_wind_alarm: ShadingPosition | None = pydantic.Field(default=ShadingPosition(0, 0), description="position for wind alarm")
    pos_sleeping_night: ShadingPosition | None = pydantic.Field(default=ShadingPosition(100, 100), description="position for sleeping at night")
    pos_sleeping_day: ShadingPosition = pydantic.Field(default=None, description="position for sleeping at day. If not given, the same as pos_sleeping_night is used")  # type:ignore[assignment]  # will be set by pydantic validator
    pos_sun_protection: ShadingPosition | None = pydantic.Field(default=ShadingPosition(100, None), description="position for sun protection")
    pos_night_close_summer: ShadingPosition | None = pydantic.Field(default=None, description="position for night close during summer")
    pos_night_close_winter: ShadingPosition | None = pydantic.Field(default=ShadingPosition(100, 100), description="position for night close during winter")
    pos_door_open: ShadingPosition | None = pydantic.Field(default=ShadingPosition(0, 0), description="position if door is opened")
    manual_timeout: int = pydantic.Field(default=24 * 3600, description="fallback timeout for manual state", gt=0)
    door_post_time: int = pydantic.Field(default=5 * 60, description="extended time after door is closed", gt=0)
    value_tolerance: int = pydantic.Field(default=0, description="value tolerance for shading position which is allowed without manual detection", ge=0)

    @pydantic.model_validator(mode="after")
    def validate_model(self) -> typing_extensions.Self:
        """Validate model.

        Returns:
            validated model
        """
        if self.pos_sleeping_night and not self.pos_sleeping_day:
            self.pos_sleeping_day = copy.deepcopy(self.pos_sleeping_night)
        return self


class ShadingConfig(ConfigBase):
    """Config for shading objects."""

    items: ShadingItems = pydantic.Field(..., description="items for shading")
    parameter: ShadingParameter = pydantic.Field(default=ShadingParameter(), description="parameter for shading")

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


class ResetAllManualHandItems(ItemBase):
    """Items for reset all manual hand items."""

    reset_manual_hand: SwitchItem = pydantic.Field(..., description="item for resetting manual and hand state to automatic state")
    any_hand_manual_is_active_feedback: SwitchItem | None = pydantic.Field(default=None, description="item which is set to ON if any hand state is active")


class ResetAllManualHandParameter(ParameterBase):
    """Parameter for reset all manual hand parameter."""

    shading_objects: list[Any] | None = pydantic.Field(default=None, description="list of shading objects to reset, if set to None, all shading objects are reset")
    custom_hand_state: list[str] = pydantic.Field(default_factory=list, description="list of custom hand states to reset. E.g. ['Auto_Open_PostOpen']")


class ResetAllManualHandConfig(ConfigBase):
    """Config for reset all manual hand config."""

    items: ResetAllManualHandItems = pydantic.Field(..., description="items for reset all manual hand config")
    parameter: ResetAllManualHandParameter = pydantic.Field(default=ResetAllManualHandParameter(), description="parameter for reset all manual hand config")


class SlatValueItems(ItemBase):
    """Items for slat values for sun protection."""

    sun_elevation: NumberItem = pydantic.Field(..., description="item for sun elevation")
    slat_value: NumberItem | DimmerItem = pydantic.Field(..., description="item for slat value, which should be set")
    summer: SwitchItem | None = pydantic.Field(default=None, description="item for summer")


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


class SlatValueParameter(ParameterBase):
    """Parameter for slat values for sun protection."""

    elevation_slat_characteristic: list[ElevationSlatMapping] = pydantic.Field(
        default=[ElevationSlatMapping(0, 100), ElevationSlatMapping(4, 100), ElevationSlatMapping(8, 90), ElevationSlatMapping(18, 80), ElevationSlatMapping(26, 70), ElevationSlatMapping(34, 60), ElevationSlatMapping(41, 50)],
        description="list of tuple-mappings from elevation to slat value",
    )
    elevation_slat_characteristic_summer: list[ElevationSlatMapping] = pydantic.Field(
        default=[ElevationSlatMapping(0, 100), ElevationSlatMapping(4, 100), ElevationSlatMapping(8, 90), ElevationSlatMapping(18, 80)], description="list of tuple-mappings from elevation to slat value, which is used if summer is active"
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


class SlatValueConfig(ConfigBase):
    """Config for slat values for sun protection."""

    items: SlatValueItems = pydantic.Field(..., description="items for slat values for sun protection")
    parameter: SlatValueParameter = pydantic.Field(default=SlatValueParameter(), description="parameter for slat values for sun protection")


class ReferenceRunItems(ItemBase):
    """Items for reference run."""

    trigger_run: SwitchItem = pydantic.Field(..., description="item for triggering the reference run")
    last_run: DatetimeItem = pydantic.Field(..., description="item for date/time of the last run")
    presence_state: StringItem = pydantic.Field(..., description="item for presence state")


class ReferenceRunConfig(ConfigBase):
    """Config for reference run."""

    items: ReferenceRunItems = pydantic.Field(..., description="items for reference run")
    parameter: None = None
