import dataclasses


@dataclasses.dataclass
class TargetState:
	presence: bool | int
	day: bool | int
	sleeping: bool | int
	target_state: bool | int

	def __post_init__(self):
		self.presence = bool(self.presence)
		self.day = bool(self.day)


config = [
	TargetState(False, False, False, False),
	TargetState(False, False, True, False),
	TargetState(False, True, False, False),
	TargetState(False, True, True, False),
	TargetState(True, False, False, False),
	TargetState(True, False, True, False),
	TargetState(True, True, False, False),
	TargetState(True, True, True, False),
]

config_2 = [
	TargetState(presence=0, day=0, sleeping=0, target_state=0),
	TargetState(presence=0, day=0, sleeping=1, target_state=0),
	TargetState(presence=0, day=1, sleeping=0, target_state=0),
	TargetState(presence=0, day=1, sleeping=1, target_state=0),
	TargetState(presence=1, day=0, sleeping=0, target_state=0),
	TargetState(presence=1, day=0, sleeping=1, target_state=0),
	TargetState(presence=1, day=1, sleeping=0, target_state=0),
	TargetState(presence=1, day=1, sleeping=1, target_state=0),
]
