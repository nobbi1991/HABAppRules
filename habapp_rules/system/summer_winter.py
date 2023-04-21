"""Rule to detect whether it is summer or winter."""
import datetime
import logging
import statistics

import HABApp

import habapp_rules.common.hysteresis
import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class SummerWinterException(Exception):
	"""Custom Exception for SummerWinter"""


class SummerWinter(HABApp.Rule):
	"""Rule check if it is summer or winter."""

	def __init__(self, outside_temperature_name: str, summer_name: str, persistence_service: str = None, days: int = 5, temperature_threshold: float = 16, last_check_name: str = None) -> None:
		"""Init rule to update summer/winter item.

		:param outside_temperature_name: Name of outside temperature item. OpenHAB-Type must be Number item
		:param summer_name: Name of summer item. OpenHAB-Type must be Switch item
		:param persistence_service: Name of persistence service
		:param days: number of days in the past which will be used to check if it is summer
		:param temperature_threshold: threshold weighted temperature for summer
		:param last_check_name: Name of last check item. OpenHAB-Type must be DateTime item
		"""
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, summer_name)

		# set class variables
		self._persistence_service = persistence_service
		self._days = days
		self._hysteresis_switch = habapp_rules.common.hysteresis.HysteresisSwitch(temperature_threshold, 0.5)
		self.__now = datetime.datetime.now()

		# get items
		self._outside_temp_item = HABApp.openhab.items.NumberItem.get_item(outside_temperature_name)
		self._item_summer = HABApp.openhab.items.SwitchItem.get_item(summer_name)
		self._item_last_check = HABApp.openhab.items.DatetimeItem.get_item(last_check_name) if last_check_name else None

		# run at init and every day at 23:00
		self.run.soon(self._cb_update_summer)
		self.run.on_every_day(datetime.time(23), self._cb_update_summer)

		LOGGER.debug("Init of Summer / Winter successful")

	def __get_weighted_mean(self, days_in_past: int) -> float:
		"""Get weighted mean temperature.

		The weighted mean temperature will be calculated according the following formula: (T07 + T14 + T22 + T22) / 4 where T07 is the temperature at 7:00 (and so on)
		It is possible to get the weighted temperature of today or of some days in the past -> defined by the days_in past attribute. If this method is called before 22:00 there will be an offset of one day.
		:param days_in_past: if days in past is set to 0 it will return the mean of today. 1 will return the offset of yesterday
		:return: the weighted mean according the formula in doc-string
		:raises SummerWinterException: if there is not enough data for at least one evaluated hour.
		"""
		day_offset = 0
		if self.__now.hour < 23:
			day_offset = 1

		temperature_values = []
		for hour in [7, 14, 22]:
			start_time = datetime.datetime(self.__now.year, self.__now.month, self.__now.day, hour, 0) - datetime.timedelta(days=day_offset + days_in_past)
			end_time = start_time + datetime.timedelta(hours=1)
			persistence_data = self._outside_temp_item.get_persistence_data(persistence=self._persistence_service, start_time=start_time, end_time=end_time)
			if not persistence_data.data:
				raise SummerWinterException(f"No data for {start_time}")
			temperature_values.append(next(iter(persistence_data.data.values())))
		return (sum(temperature_values) + temperature_values[2]) / 4

	def __is_summer(self) -> bool:
		"""Check if it is summer (or winter).

		:return: Returns True if it is summer.
		:raises SummerWinterException: if summer/winter could not be detected
		"""
		self.__now = datetime.datetime.now()
		values = []
		for day in range(self._days):
			try:
				values.append(self.__get_weighted_mean(day))
			except SummerWinterException:
				self._instance_logger.warning(f"Could not get mean value of day -{day}")

		if not values:
			raise SummerWinterException("Not enough data to detect summer/winter")

		is_summer = self._hysteresis_switch.get_output(mean_value := statistics.mean(values))
		self._instance_logger.debug(f"Check Summer/Winter. values = {values} | mean = {mean_value} | summer = {is_summer}")
		return is_summer

	def _cb_update_summer(self) -> None:
		"""Callback to update the summer item."""
		try:
			is_summer = self.__is_summer()
		except SummerWinterException:
			self._instance_logger.error("Could not get summer / winter")
			return

		# get target state of summer
		target_value = "ON" if is_summer else "OFF"

		# send state
		if self._item_summer.value != target_value:
			self._item_summer.oh_send_command(target_value)
			self._instance_logger.info(f"Summer changed to {target_value}")

		# update last update item at every call
		if self._item_last_check:
			self._item_last_check.oh_send_command(datetime.datetime.now())
