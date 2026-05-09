"""Module for hysteresis switch."""

import logging

LOGGER = logging.getLogger(__name__)


class HysteresisSwitch:
    """Hysteresis switch."""

    def __init__(self, threshold_on: float, hysteresis: float) -> None:
        """Switch with hysteresis.

        Args:
            threshold_on: threshold for switching on
            hysteresis: hysteresis offset: threshold_off = threshold_on -hysteresis_offset
        """
        self._threshold = threshold_on
        self._hysteresis = hysteresis
        self._on_off_state = False
        self._value_last = 0.0

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

    def get_output(self, value: float | None = None) -> bool:
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
        if value:
            self._value_last = value
        return self._on_off_state

    def get_output_as_string(self, value: float | None) -> str:
        """Get output of hysteresis as string.

        Args:
            value: value which should be checked

        Returns:
            "ON" / "OFF"state as string
        """
        bool_output = self.get_output(value)

        return "ON" if bool_output else "OFF"
