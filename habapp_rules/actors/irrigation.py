"""Rules to for garden watering."""
import datetime
import logging

import HABApp

import habapp_rules.core.exceptions
import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class Irrigation(HABApp.Rule):
	"""Rule for easy irrigation control.

	# Items:
    Switch     I999_valve                   "Valve state"           {channel="some_channel_config"}
	Switch     I999_irrigation_active       "Irrigation active"
	Number     I999_irrigation_hour         "Start hour [%d]"
	Number     I999_irrigation_minute       "Start minute[%d]"
	Number     I999_irrigation_duration     "Duration [%d]"

	# Rule init:
	habapp_rules.actors.irrigation.Irrigation("I999_valve", "I999_irrigation_active", "I999_irrigation_hour", "I999_irrigation_minute", "I999_irrigation_duration")
	"""

	def __init__(self, name_valve: str, name_active: str, name_hour: str, name_minute: str, name_duration: str, name_repetitions: str | None = None, name_brake: str | None = None):
		"""Init of irrigation object.

		:param name_valve: name of OpenHAB valve item (SwitchItem)
		:param name_active: name of OpenHAB irrigation activation item (SwitchItem)
		:param name_hour: name of OpenHAB item for defining the start hour (NumberItem)
		:param name_minute: name of OpenHAB item for defining the start minute (NumberItem)
		:param name_duration: name of OpenHAB item for defining the duration (NumberItem)
		:param name_repetitions: [optional] name of OpenHAB item for defining the number of repetitions (NumberItem)
		:param name_brake: [optional] name of OpenHAB item for defining brake time in minutes between the repetitions (NumberItem)
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if configuration is not correct
		"""

		if bool(name_repetitions) != bool(name_brake):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException("If repeats item is given, also the brake item must be given!")

		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_valve)

		self._item_valve = HABApp.openhab.items.SwitchItem.get_item(name_valve)
		self._item_active = HABApp.openhab.items.SwitchItem.get_item(name_active)
		self._item_hour = HABApp.openhab.items.NumberItem.get_item(name_hour)
		self._item_minute = HABApp.openhab.items.NumberItem.get_item(name_minute)
		self._item_duration = HABApp.openhab.items.NumberItem.get_item(name_duration)
		self._item_repetitions = HABApp.openhab.items.NumberItem.get_item(name_repetitions) if name_repetitions else None
		self._item_brake = HABApp.openhab.items.NumberItem.get_item(name_brake) if name_brake else None

		self.run.soon(self._cb_set_valve_state)
		self.run.every_minute(self._cb_set_valve_state)

		self._item_active.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_minute.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._item_hour.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._item_repetitions and self._item_brake:
			self._item_repetitions.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())
			self._item_brake.listen_event(self._cb_set_valve_state, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with name '{self.rule_name}' was successful.")

	def _get_target_valve_state(self) -> bool:
		"""Get target valve state, depending on the OpenHAB item states

		:return: True if valve should be on, otherwise False
		:raises habapp_rules.core.exceptions.HabAppRulesException: if value for hour / minute / duration is not valid
		"""
		if not self._item_active:
			return False

		if any(item.value is None for item in (self._item_hour, self._item_minute, self._item_duration)):
			raise habapp_rules.core.exceptions.HabAppRulesException(
				f"OpenHAB item values are not valid for hour / minute / duration. See current values: hour={self._item_hour.value} | minute={self._item_minute.value} | duration={self._item_duration.value}")

		repetitions = self._item_repetitions.value if self._item_repetitions else 0
		brake = self._item_brake.value if self._item_brake else 0

		now = datetime.datetime.now()

		for idx in range(repetitions + 1):
			start_time = datetime.datetime.combine(date=now, time=datetime.time(self._item_hour.value, self._item_minute.value)) + datetime.timedelta(minutes=idx * (self._item_duration.value + brake))
			end_time = start_time + datetime.timedelta(minutes=self._item_duration.value)
			if self._is_in_time_range(start_time.time(), end_time.time(), now.time()):
				return True
		return False

	@staticmethod
	def _is_in_time_range(start_time: datetime.time, end_time: datetime.time, time_to_check: datetime.time) -> bool:
		"""Check if a time is in a given range.

		:param start_time: start time of the time range
		:param end_time: end time of the time range
		:param time_to_check: time, which should be checked
		:return: True if the time, which should be checked is between start and stop time
		"""
		if end_time < start_time:
			return start_time <= time_to_check or end_time > time_to_check
		return start_time <= time_to_check < end_time

	def _cb_set_valve_state(self, _: HABApp.openhab.events.ItemStateChangedEvent | None = None) -> None:
		"""Callback to set the valve state, triggered by cyclic call or item event"""
		try:
			target_value = self._get_target_valve_state()
		except habapp_rules.core.exceptions.HabAppRulesException as exc:
			self._instance_logger.warning(f"Could not get target valve state, set it to false. Error: {exc}")
			target_value = False

		if bool(self._item_valve) != target_value:
			self._instance_logger.info(f"Valve state changed to {target_value}")
			self._item_valve.oh_send_command("ON" if target_value else "OFF")
