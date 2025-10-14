"""Rules to handle sun sensors."""

import logging

import HABApp

import habapp_rules.common.config.filter
import habapp_rules.common.filter
import habapp_rules.common.hysteresis
import habapp_rules.core.helper
import habapp_rules.core.logger
import habapp_rules.sensors.config.sun
from habapp_rules.core.helper import send_if_different
from habapp_rules.system import PresenceState

LOGGER = logging.getLogger(__name__)


class _SensorBase(HABApp.Rule):
    """Base class for sun sensors."""

    def __init__(self, config: habapp_rules.sensors.config.sun.BrightnessConfig | habapp_rules.sensors.config.sun.TemperatureDifferenceConfig, item_input: HABApp.openhab.items.NumberItem) -> None:
        """Init of base class for sun sensors.

        Args:
            config: config for sun sensor
            item_input: item for input value (brightness or temperature difference)
        """
        self._config = config

        # init HABApp Rule
        HABApp.Rule.__init__(self)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, config.items.output.name)

        # init exponential filter
        name_input_exponential_filtered = f"H_{item_input.name.removeprefix('H_')}_filtered"
        habapp_rules.core.helper.create_additional_item(name_input_exponential_filtered, "Number", name_input_exponential_filtered.replace("_", " "), config.parameter.filtered_signal_groups)
        item_input_filtered = HABApp.openhab.items.NumberItem.get_item(name_input_exponential_filtered)

        exponential_filter_config = habapp_rules.common.config.filter.ExponentialFilterConfig(
            items=habapp_rules.common.config.filter.ExponentialFilterItems(raw=item_input, filtered=item_input_filtered),
            parameter=habapp_rules.common.config.filter.ExponentialFilterParameter(tau=config.parameter.filter_tau, instant_increase=config.parameter.filter_instant_increase, instant_decrease=config.parameter.filter_instant_decrease),
        )
        habapp_rules.common.filter.ExponentialFilter(exponential_filter_config)

        # attributes
        self._hysteresis_switch = habapp_rules.common.hysteresis.HysteresisSwitch(config.threshold, config.parameter.hysteresis, return_bool=False)

        # callbacks
        item_input_filtered.listen_event(self._cb_input_filtered, HABApp.openhab.events.ItemStateChangedEventFilter())
        if config.items.threshold is not None:
            config.items.threshold.listen_event(self._cb_threshold, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _send_output(self, new_value: str) -> None:
        """Send output if different.

        Args:
            new_value: new value which should be sent
        """
        if new_value != self._config.items.output.value:
            self._config.items.output.oh_send_command(new_value)
            self._instance_logger.debug(f"Set output '{self._config.items.output.name}' to {new_value}")

    def _cb_input_filtered(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the filtered input value changed.

        Args:
            event: trigger event
        """
        value = self._hysteresis_switch.get_output(event.value)
        self._send_output(value)

    def _cb_threshold(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is triggered if the threshold changed.

        Args:
            event: trigger event
        """
        self._hysteresis_switch.set_threshold_on(event.value)


class SensorBrightness(_SensorBase):
    """Rules class to set sun protection depending on brightness level.

    # Items:
    Number    brightness                    "Current brightness"               {channel="..."}
    Number    brightness_threshold          "Brightness threshold"
    Switch    sun_protection_brightness     "Sun protection brightness"        {channel="..."}

    # Config:
    config = habapp_rules.sensors.config.sun.BrightnessConfig(
            items=habapp_rules.sensors.config.sun.BrightnessItems(
                    brightness="brightness",
                    output="sun_protection_brightness",
                    brightness_threshold="brightness_threshold"
            )
    )

    # Rule init:
    habapp_rules.sensors.sun.SensorBrightness(config)
    """

    def __init__(self, config: habapp_rules.sensors.config.sun.BrightnessConfig) -> None:
        """Init of sun sensor which takes a brightness value.

        Args:
            config: config for the sun sensor which is using brightness
        """
        _SensorBase.__init__(self, config, config.items.brightness)


class SensorTemperatureDifference(_SensorBase):
    """Rules class to set sun protection depending on temperature difference. E.g. temperature in the sun / temperature in the shadow.

    # Items:
    Number    temperature_sun               "Temperature sun"               {channel="..."}
    Number    temperature_shadow            "Temperature shadow"            {channel="..."}
    Number    temperature_threshold         "Temperature threshold"
    Switch    sun_protection_temperature    "Sun protection temperature"    {channel="..."}

    # Config:
    config = habapp_rules.sensors.config.sun.TemperatureDifferenceConfig(
            items=habapp_rules.sensors.config.sun.TemperatureDifferenceItems(
                    temperatures=["temperature_sun", "temperature_shadow"],
                    output="sun_protection_temperature",
                    threshold="temperature_threshold"
            )
    )

    # Rule init:
    habapp_rules.sensors.sun.SensorTempDiff(config)
    """

    def __init__(self, config: habapp_rules.sensors.config.sun.TemperatureDifferenceConfig) -> None:
        """Init of sun sensor which takes a two or more temperature values (one in the sun and one in the shadow).

        Args:
            config: config for the sun sensor which is using temperature items
        """
        self._config = config
        name_temperature_diff = f"H_Temperature_diff_for_{config.items.output.name}"
        habapp_rules.core.helper.create_additional_item(name_temperature_diff, "Number", name_temperature_diff.replace("_", " "), config.parameter.filtered_signal_groups)
        self._item_temp_diff = HABApp.openhab.items.NumberItem.get_item(name_temperature_diff)

        _SensorBase.__init__(self, config, self._item_temp_diff)

        # callbacks
        for temperature_item in self._config.items.temperatures:
            temperature_item.listen_event(self._cb_temperature, HABApp.openhab.events.ItemStateChangedEventFilter())

        # calculate temperature difference
        self._cb_temperature(None)

    def _cb_temperature(self, _: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
        """Callback, which is triggered if a temperature value changed."""
        filtered_items = [itm for itm in habapp_rules.core.helper.filter_updated_items(self._config.items.temperatures, self._config.parameter.ignore_old_values_time) if itm.value is not None]
        if len(filtered_items) < 2:  # noqa: PLR2004
            return
        value_min = min(item.value for item in filtered_items)
        value_max = max(item.value for item in filtered_items)

        self._item_temp_diff.oh_send_command(value_max - value_min)


class SunPositionFilter(HABApp.Rule):
    """Rules class to filter a switch state depending on the sun position. This can be used to only close the blinds of a window, if the sun hits the window.

    # Items:
    Number    sun_azimuth           "Sun Azimuth"                       {channel="astro..."}
    Number    sun_elevation         "Sun Elevation"                     {channel="astro..."}
    Switch    sun_shining           "Sun is shining"
    Switch    sun_hits_window       "Sun hits window"

    # Config:
    config = habapp_rules.sensors.config.sun.SunPositionConfig(
            items=habapp_rules.sensors.config.sun.SunPositionItems(
                    azimuth="sun_azimuth",
                    elevation="sun_elevation",
                    input="sun_shining",
                    output="sun_hits_window"
            ),
            parameter=habapp_rules.sensors.config.sun.SunPositionParameter(
                    sun_position_window=habapp_rules.sensors.config.sun.SunPositionWindow(40, 120)
            )
    )

    # Rule init:

    habapp_rules.sensors.sun.SunPositionFilter(config)
    """

    def __init__(self, config: habapp_rules.sensors.config.sun.SunPositionConfig) -> None:
        """Init of sun position filter.

        Args:
            config: config for the sun position filter
        """
        self._config = config

        # init HABApp Rule
        HABApp.Rule.__init__(self)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, config.items.output.name)

        # callbacks
        config.items.azimuth.listen_event(self._update_output, HABApp.openhab.events.ItemStateChangedEventFilter())  # listen_event for elevation is not needed because elevation and azimuth is updated together
        config.items.input.listen_event(self._update_output, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._update_output(None)

    def _sun_in_window(self, azimuth: float, elevation: float) -> bool:
        """Check if the sun is in the 'sun window' where it hits the target.

        Args:
            azimuth: azimuth of the sun
            elevation: elevation of the sun

        Returns:
            True if the sun hits the target, else False
        """
        sun_in_window = False

        if any(window.azimuth_min <= azimuth <= window.azimuth_max and window.elevation_min <= elevation <= window.elevation_max for window in self._config.parameter.sun_position_windows):
            sun_in_window = True

        return sun_in_window

    def _update_output(self, _: HABApp.openhab.events.ItemStateChangedEvent | None) -> None:
        """Callback, which is triggered if the sun position or input changed."""
        azimuth = self._config.items.azimuth.value
        elevation = self._config.items.elevation.value

        if azimuth is None or elevation is None:
            self._instance_logger.warning(f"Azimuth or elevation is None -> will set output to input. azimuth = {azimuth} | elevation = {elevation}")
            filter_output = self._config.items.input.value
        elif self._config.items.input.value in {"OFF", None}:
            filter_output = "OFF"
        else:
            filter_output = "ON" if self._sun_in_window(azimuth, elevation) else "OFF"

        if filter_output != self._config.items.output.value:
            self._config.items.output.oh_send_command(filter_output)


class WinterFilter(HABApp.Rule):
    """Rule to filter the sun sensor depending on heating and presence state.

    # Items:
    Switch      sun             "Sun is shining"
    Switch      heating_active  "Heating is active"
    Switch      sun_filtered    "Sun filtered"

    # Config:
    config = habapp_rules.sensors.config.sun.WinterFilterConfig(
        items=habapp_rules.sensors.config.sun.WinterFilterItems(
            sun="sun",
            heating_active="heating_active",
            output="sun_filtered",
        )
    )

    # Rule init:
    habapp_rules.sensors.sun.WinterFilter(config)
    """

    def __init__(self, config: habapp_rules.sensors.config.sun.WinterFilterConfig) -> None:
        """Init of sun position filter.

        Args:
            config: config for the sun position filter
        """
        HABApp.Rule.__init__(self)
        self._config = config

        # callbacks
        config.items.sun.listen_event(self._cb_sun, HABApp.openhab.events.ItemStateChangedEventFilter())
        if config.items.heating_active is not None:
            config.items.heating_active.listen_event(self._cb_heating, HABApp.openhab.events.ItemStateChangedEventFilter())
        if config.items.presence_state is not None:
            config.items.presence_state.listen_event(self.cb_presence_state, HABApp.openhab.events.ItemStateChangedEventFilter())

        self._check_conditions_and_set_output()

    def _check_conditions_and_set_output(self) -> None:
        """Check conditions and set output.

        The output will be on, if the sun is up, the heating is off and somebody is at home.
        """
        heating_on = self._config.items.heating_active.is_on()
        absence = self._config.items.presence_state.value != PresenceState.PRESENCE.value if self._config.items.presence_state is not None else True

        target_state = self._config.items.sun.is_on() and (not heating_on or not absence)
        send_if_different(self._config.items.output, "ON" if target_state else "OFF")

    def _cb_sun(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa: ARG002
        """Callback which is triggered if sun state changed.

        Args:
            event: original trigger event
        """
        self._check_conditions_and_set_output()

    def _cb_heating(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa: ARG002
        """Callback which is triggered if heating state changed.

        Args:
            event: original trigger event
        """
        self._check_conditions_and_set_output()

    def cb_presence_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa: ARG002
        """Callback which is triggered if presence_state changed.

        Args:
            event: original trigger event
        """
        self._check_conditions_and_set_output()
