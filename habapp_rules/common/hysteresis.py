"""Module for hysteresis switch"""


class HysteresisSwitch:
	"""Hysteresis switch"""

	def __init__(self, threshold_on: float, hysteresis: float, return_bool: bool = True):
		"""Switch with hysteresis
		:param threshold_on: threshold for switching on
		:param hysteresis: hysteresis offset: threshold_off = threshold_on -hysteresis_offset
		:param return_bool: choose return-type: if true bool will be returned, else 'ON' / 'OFF'
		"""
		self._threshold = threshold_on
		self._hysteresis = hysteresis
		self._return_bool = return_bool
		self._on_off_state = False
		self._value_last = 0

	def set_threshold_on(self, threshold_on: float) -> None:
		"""Update threshold.

		:param threshold_on: new threshold value
		"""
		self._threshold = threshold_on

	def get_output(self, value: float | None = None) -> bool | str:
		"""Get output of hysteresis switch
		:param value: value which should be checked
		:return: on / off state
		"""
		# get threshold depending on the current state
		threshold = self._threshold - 0.5 * self._hysteresis if self._on_off_state else self._threshold + 0.5 * self._hysteresis

		# use new value if given, otherwise last value
		value = value if value else self._value_last

		# save value for next check
		self._value_last = value

		# get on / off state
		self._on_off_state = value >= threshold

		# if on/off result is requested convert result
		if self._return_bool:
			return self._on_off_state

		return "ON" if self._on_off_state else "OFF"
