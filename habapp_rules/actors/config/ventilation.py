"""Configuration of ventilation."""
import dataclasses
import datetime

import habapp_rules.core.exceptions


@dataclasses.dataclass
class VentilationConfig:
	"""Config for ventilation."""
	hand_timeout: int
	normal_level: int = 1
	power_hand_level: int = 2
	power_external_level: int = 2
	display_text_external: str = "External"
	display_text_humidity: str = "Humidity"  # only used for VentilationHeliosTwoStageHumidity
	long_absence_duration: int = 3600
	long_absence_power_start_time: datetime.time = datetime.time(6)
	long_absence_level: int = 1

	def __post_init__(self) -> None:
		"""Validate config after init.

		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if given values are not valid
		"""
		if not isinstance(self.long_absence_power_start_time, datetime.time):
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"'long_absence_power_start_time' must be of type 'datetime.time'. Given type: {type(self.long_absence_power_start_time)}")


CONFIG_DEFAULT = VentilationConfig(3600)
