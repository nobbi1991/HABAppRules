"""Config for HCL color"""
import dataclasses


@dataclasses.dataclass
class LightHclConfig:
	"""Config for HCL color"""
	color_config: list[tuple[float, float]]
	hand_timeout: int = 5 * 3600  # 5 hours
	sleep_color: float | None = None
	post_sleep_timeout: int | None = None
	focus_color: float | None = None
	shift_weekend_holiday: bool = False  # only relevant for HclTime

	def __post_init__(self) -> None:
		"""Trigger checks after init."""
		self._sorted_color_config()

	def _sorted_color_config(self) -> None:
		"""Sort color config"""
		self.color_config = sorted(self.color_config, key=lambda x: x[0])


EXAMPLE_CONFIG_ELEVATION = LightHclConfig([
	(-15, 3900),
	(0, 4500),
	(5, 5500),
	(15, 6500)
])

EXAMPLE_CONFIG_TIME = LightHclConfig([
	(0, 2200),
	(4, 2200),
	(5, 3200),
	(6, 3940),
	(8, 5000),
	(12, 7000),
	(19, 7000),
	(21, 5450),
	(22, 4000),
	(23, 2600),
])
