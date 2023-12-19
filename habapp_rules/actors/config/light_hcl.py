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
