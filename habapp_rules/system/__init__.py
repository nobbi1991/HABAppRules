"""States of all system state machines."""

import enum


class SleepState(enum.Enum):
    """Sleep states."""

    AWAKE = "Awake"
    PRE_SLEEPING = "PreSleeping"
    SLEEPING = "Sleeping"
    POST_SLEEPING = "PostSleeping"
    LOCKED = "Locked"


class PresenceState(enum.Enum):
    """Presence states."""

    PRESENCE = "Presence"
    LEAVING = "Leaving"
    ABSENCE = "Absence"
    LONG_ABSENCE = "LongAbsence"
