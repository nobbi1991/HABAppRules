"""Rules for astro actions."""

import abc
import logging

import HABApp
from HABApp.openhab.events import ItemStateChangedEvent
from HABApp.openhab.events.event_filters import ItemStateChangedEventFilter
from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.core.helper import send_if_different
from habapp_rules.sensors.config.astro import SetDayConfig, SetNightConfig

LOGGER = logging.getLogger(__name__)


class _SetNightDayBase(abc.ABC, HABApp.Rule):
    """Base class for set night / day."""

    def __init__(self, item_target: SwitchItem, item_elevation: NumberItem, elevation_threshold: float) -> None:
        """Init Rule.

        Args:
            item_target: OpenHab item which should be set depending on the sun elevation value
            item_elevation: OpenHAB item of sun elevation (NumberItem)
            elevation_threshold: Threshold value for elevation.
        """
        HABApp.Rule.__init__(self)

        self._item_target = item_target
        self._item_elevation = item_elevation
        self._elevation_threshold = elevation_threshold

        self._item_elevation.listen_event(self._set_night, ItemStateChangedEventFilter())

        self.run.soon(self._set_night, None)

    def _set_night(self, _: ItemStateChangedEvent | None = None) -> None:
        """Callback which sets the state to the night item."""
        if self._item_elevation.value is None:
            return
        send_if_different(self._item_target, self._get_target_value())

    @abc.abstractmethod
    def _get_target_value(self) -> str:
        """Get target value which should be set.

        Returns:
            target value (ON / OFF)
        """


class SetDay(_SetNightDayBase):
    """Rule to set / unset day item at dusk / dawn.

    # Items:
    Switch    day                   "Day"
    Number    elevation             "Sun elevation"    <sun>     {channel="astro...}

    # Config:
    config = SetDayConfig(
            items=SetDayItems(
                    day="day",
                    elevation="elevation"
            ),
            parameter=SetDayParameter(
                    elevation_threshold=5
            )
    )

    # Rule init:
    SetDay(config)
    """

    def __init__(self, config: SetDayConfig) -> None:
        """Init Rule.

        Args:
            config: Config for set day rule
        """
        _SetNightDayBase.__init__(self, config.items.day, config.items.elevation, config.parameter.elevation_threshold)

    def _get_target_value(self) -> str:
        """Get target value which should be set.

        Returns:
            target value (ON / OFF)
        """
        return "ON" if self._item_elevation.value > self._elevation_threshold else "OFF"


class SetNight(_SetNightDayBase):
    """Rule to set / unset night item at dusk / dawn.

    # Items:
    Switch    night_for_shading     "Night for shading"
    Number    elevation             "Sun elevation"    <sun>     {channel="astro...}

    # Config:
    config = SetNightConfig(
            items=SetNightItems(
                    night="night",
                    elevation="elevation"
            ),
            parameter=SetNightParameter(
                    elevation_threshold=5
            )
    )

    # Rule init:
    SetNight(config)
    """

    def __init__(self, config: SetNightConfig) -> None:
        """Init Rule.

        Args:
            config: Config for setting night depending on sun elevation
        """
        _SetNightDayBase.__init__(self, config.items.night, config.items.elevation, config.parameter.elevation_threshold)

    def _get_target_value(self) -> str:
        """Get target value which should be set.

        Returns:
            target value (ON / OFF)
        """
        return "ON" if self._item_elevation.value < self._elevation_threshold else "OFF"
