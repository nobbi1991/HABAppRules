"""States of all system state machines."""

import enum


class SleepState(enum.Enum):
    """Sleep states."""

    AWAKE = "awake"
    PRE_SLEEPING = "pre_sleeping"
    SLEEPING = "sleeping"
    POST_SLEEPING = "post_sleeping"
    LOCKED = "locked"


class PresenceState(enum.Enum):
    """Presence states."""

    PRESENCE = "presence"
    LEAVING = "leaving"
    ABSENCE = "absence"
    LONG_ABSENCE = "long_absence"
