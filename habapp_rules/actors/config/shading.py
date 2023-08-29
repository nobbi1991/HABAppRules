"""Configuration of shading objects."""

import dataclasses


@dataclasses.dataclass
class ShadingPosition:
	"""Position of shading object"""
	position: float | bool | None
	slat: float | None = None


@dataclasses.dataclass
class ShadingConfig:
	"""Config for shading objects.

	A value of 0 of manual_timeout will disable the timeout of the manual state
	"""
	pos_auto_open: ShadingPosition
	pos_wind_alarm: ShadingPosition | None = None
	pos_sleeping: ShadingPosition | None = None
	pos_sun_protection: ShadingPosition | None = None
	pos_night_close_summer: ShadingPosition | None = None
	pos_night_close_winter: ShadingPosition | None = None
	pos_door_open: ShadingPosition | None = None
	manual_timeout: int = 0
	door_post_time: int = 5 * 60

	def __post_init__(self) -> None:
		"""Validate configuration.

		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if configuration is not valid
		"""
		if self.door_post_time in {0, None}:
			self.door_post_time = 1


CONFIG_DEFAULT = ShadingConfig(
	pos_auto_open=ShadingPosition(0, 0),
	pos_wind_alarm=ShadingPosition(0, 0),
	pos_sleeping=ShadingPosition(100, 100),
	pos_sun_protection=ShadingPosition(100, None),
	pos_night_close_summer=None,
	pos_night_close_winter=ShadingPosition(100, 100),
	pos_door_open=ShadingPosition(0, 0),
	manual_timeout=24 * 3600,
	door_post_time=5,
)

CONFIG_DEFAULT_ELEVATION_SLAT_WINTER = [(0, 100), (4, 100), (8, 90), (18, 80), (26, 70), (34, 60), (41, 50), (42, 50), (90, 50), ]
CONFIG_DEFAULT_ELEVATION_SLAT_SUMMER = [(0, 100), (4, 100), (8, 100), (18, 100), (26, 100), (34, 90), (41, 80), (42, 80), (90, 80), ]
