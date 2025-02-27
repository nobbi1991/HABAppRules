"""Module for hysteresis switch."""

import logging

LOGGER = logging.getLogger(__name__)


class HysteresisSwitch:
    """Hysteresis switch."""

    def __init__(self, threshold_on: float, hysteresis: float, return_bool: bool = True) -> None:
        """Switch with hysteresis.

        Args:
            threshold_on: threshold for switching on
            hysteresis: hysteresis offset: threshold_off = threshold_on -hysteresis_offset
            return_bool: choose return-type: if true bool will be returned, else 'ON' / 'OFF'.
        """
        self._threshold = threshold_on
        self._hysteresis = hysteresis
        self._return_bool = return_bool
        self._on_off_state = False
        self._value_last = 0

    def set_threshold_on(self, threshold_on: float) -> None:
        """Update threshold.

        Args:
            threshold_on: new threshold value
        """
        self._threshold = threshold_on
        if self._hysteresis == float("inf"):  # needed for habapp_rules.sensors.motion
            new_threshold = 0.1 * threshold_on
            LOGGER.warning(f"Hysteresis was not set and changed to {new_threshold} | threshold = {threshold_on}")
            self._hysteresis = new_threshold

    def get_output(self, value: float | None = None) -> bool | str:
        """Get output of hysteresis switch.

        Args:
            value: value which should be checked

        Returns:
            on / off state.
        """
        if self._threshold:
            # get threshold depending on the current state
            threshold = self._threshold - 0.5 * self._hysteresis if self._on_off_state else self._threshold + 0.5 * self._hysteresis

            # use new value if given, otherwise last value
            value = value if value is not None else self._value_last

            # get on / off state
            self._on_off_state = value >= threshold
        else:
            LOGGER.warning(f"Can not get output value for value = '{value}'. Threshold is not set correctly. self._threshold = {self._threshold}")
            self._on_off_state = False

        # save value for next check
        self._value_last = value

        # if on/off result is requested convert result
        if self._return_bool:
            return self._on_off_state

        return "ON" if self._on_off_state else "OFF"
