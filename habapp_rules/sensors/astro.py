"""Rules for astro actions."""

import abc
import logging

import HABApp

import habapp_rules.core.helper
import habapp_rules.sensors.config.astro

LOGGER = logging.getLogger(__name__)


class _SetNightDayBase(HABApp.Rule):
    """Base class for set night / day."""

    def __init__(self, item_target: HABApp.openhab.items.SwitchItem, item_elevation: HABApp.openhab.items.NumberItem, elevation_threshold: float) -> None:
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

        self._item_elevation.listen_event(self._set_night, HABApp.openhab.events.ItemStateChangedEventFilter())

        self.run.soon(self._set_night)

    def _set_night(self, _: HABApp.openhab.events.ItemStateChangedEvent | None = None) -> None:
        """Callback which sets the state to the night item."""
        if self._item_elevation.value is None:
            return
        habapp_rules.core.helper.send_if_different(self._item_target, self._get_target_value())

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
    config = habapp_rules.sensors.config.astro.SetDayConfig(
            items=habapp_rules.sensors.config.astro.SetDayItems(
                    day="day",
                    elevation="elevation"
            ),
            parameter=habapp_rules.sensors.config.astro.SetDayParameter(
                    elevation_threshold=5
            )
    )

    # Rule init:
    habapp_rules.sensors.astro.SetNight(config)
    """

    def __init__(self, config: habapp_rules.sensors.config.astro.SetDayConfig) -> None:
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
    config = habapp_rules.sensors.config.astro.SetNightConfig(
            items=habapp_rules.sensors.config.astro.SetNightItems(
                    night="night_for_shading",
                    elevation="elevation"
            ),
            parameter=habapp_rules.sensors.config.astro.SetNightParameter(
                    elevation_threshold=5
            )
    )

    # Rule init:
    habapp_rules.sensors.astro.SetNight(config)
    """

    def __init__(self, config: habapp_rules.sensors.config.astro.SetNightConfig) -> None:
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
