"""Rule to detect whether it is summer or winter."""

import datetime
import logging
import statistics

import HABApp

import habapp_rules.common.hysteresis
import habapp_rules.core.logger
import habapp_rules.system.config.summer_winter

LOGGER = logging.getLogger(__name__)


class SummerWinterError(Exception):
    """Custom Exception for SummerWinter."""


class SummerWinter(HABApp.Rule):
    """Rule check if it is summer or winter."""

    def __init__(self, config: habapp_rules.system.config.summer_winter.SummerWinterConfig) -> None:
        """Init rule to update summer/winter item.

        Args:
            config: Config for summer/winter detection
        """
        self._config = config
        HABApp.Rule.__init__(self)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, config.items.summer.name)

        # set class variables
        self._hysteresis_switch = habapp_rules.common.hysteresis.HysteresisSwitch(config.parameter.temperature_threshold, 0.5)
        self.__now = datetime.datetime.now()

        # run at init and every day at 23:00
        self.run.soon(self._cb_update_summer)
        self.run.at(self.run.trigger.time("23:00:00"), self._cb_update_summer)

        LOGGER.debug("Init of Summer / Winter successful")

    def __get_weighted_mean(self, days_in_past: int) -> float:
        """Get weighted mean temperature.

        The weighted mean temperature will be calculated according the following formula: (T07 + T14 + T22 + T22) / 4 where T07 is the temperature at 7:00 (and so on)
        It is possible to get the weighted temperature of today or of some days in the past -> defined by the days_in past attribute. If this method is called before 22:00 there will be an offset of one day.

        Args:
            days_in_past: if days in past is set to 0 it will return the mean of today. 1 will return the offset of yesterday

        Returns:
            the weighted mean according the formula in doc-string

        Raises:
            SummerWinterError: if there is not enough data for at least one evaluated hour.
        """
        day_offset = 0
        if self.__now.hour < 23:  # noqa: PLR2004
            day_offset = 1

        temperature_values = []
        for hour in [7, 14, 22]:
            start_time = datetime.datetime(self.__now.year, self.__now.month, self.__now.day, hour, 0) - datetime.timedelta(days=day_offset + days_in_past)
            end_time = start_time + datetime.timedelta(hours=1)
            persistence_data = self._config.items.outside_temperature.get_persistence_data(persistence=self._config.parameter.persistence_service, start_time=start_time, end_time=end_time)
            if not persistence_data.data:
                msg = f"No data for {start_time}"
                raise SummerWinterError(msg)
            temperature_values.append(next(iter(persistence_data.data.values())))
        return (sum(temperature_values) + temperature_values[2]) / 4

    def __is_summer(self) -> bool:
        """Check if it is summer (or winter).

        Returns:
            Returns True if it is summer.

        Raises:
            SummerWinterError: if summer/winter could not be detected
        """
        self.__now = datetime.datetime.now()
        values = []
        for day in range(self._config.parameter.days):
            try:
                values.append(self.__get_weighted_mean(day))
            except SummerWinterError:  # noqa: PERF203
                self._instance_logger.warning(f"Could not get mean value of day -{day}")

        if not values:
            msg = "Not enough data to detect summer/winter"
            raise SummerWinterError(msg)

        is_summer = self._hysteresis_switch.get_output(mean_value := statistics.mean(values))
        self._instance_logger.debug(f"Check Summer/Winter. values = {values} | mean = {mean_value} | summer = {is_summer}")
        return is_summer

    def _cb_update_summer(self) -> None:
        """Callback to update the summer item."""
        try:
            is_summer = self.__is_summer()
        except SummerWinterError:
            self._instance_logger.exception("Could not get summer / winter")
            return

        # get target state of summer
        target_value = "ON" if is_summer else "OFF"

        # send state
        if self._config.items.summer.value != target_value:
            self._instance_logger.info(f"Summer changed to {target_value}")
        self._config.items.summer.oh_send_command(target_value)

        # update last update item at every call
        if self._config.items.last_check is not None:
            self._config.items.last_check.oh_send_command(datetime.datetime.now())
