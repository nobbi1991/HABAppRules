import dataclasses


@dataclasses.dataclass
class PowerSwitchConfig:
	max_on_time: int | None = None
	hand_timeout: int | None = None

	absence_target_state: bool | None = None
	presence_target_state: bool | None = None
	sleeping_target_state: bool | None = None
