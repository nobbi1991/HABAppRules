"""Configuration of ventilation."""
import dataclasses
import datetime


@dataclasses.dataclass
class StateConfig:
	"""Basic state config."""
	level: int
	display_text: str


@dataclasses.dataclass
class StateConfigWithTimeout(StateConfig):
	"""State config with timeout."""
	timeout: int


@dataclasses.dataclass
class StateConfigLongAbsence(StateConfig):
	"""State config for long absence state."""
	duration: int
	start_time: datetime.time = datetime.time(6)


@dataclasses.dataclass
class VentilationConfig:
	"""Config for ventilation."""
	state_normal: StateConfig = dataclasses.field(default_factory=lambda: StateConfig(1, "Normal"))
	state_hand: StateConfigWithTimeout = dataclasses.field(default_factory=lambda: StateConfigWithTimeout(2, "Hand", 3600))
	state_external: StateConfig = dataclasses.field(default_factory=lambda: StateConfig(2, "Humidity"))
	state_humidity: StateConfig = dataclasses.field(default_factory=lambda: StateConfig(2, "Humidity"))
	state_long_absence: StateConfigLongAbsence = dataclasses.field(default_factory=lambda: StateConfigLongAbsence(2, "LongAbsence", 3600, datetime.time(6)))
	state_after_run: StateConfig = dataclasses.field(default_factory=lambda: StateConfig(2, "After run"))  # only used for Helios ventilation


CONFIG_DEFAULT = VentilationConfig()
