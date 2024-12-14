"""Get type of day."""

import datetime

import holidays

_BY_HOLIDAYS = holidays.country_holidays("DE", "BY")


def is_weekend(offset_days: int = 0) -> bool:
    """Check if current (or offset day) is a weekend day.

    Args:
        offset_days: 0 means today, 1 tomorrow, -1 yesterday

    Returns:
        True if desired day is a weekend day
    """
    day_to_check = datetime.datetime.now() + datetime.timedelta(days=offset_days)
    return day_to_check.isoweekday() in {6, 7}


def is_holiday(offset_days: int = 0) -> bool:
    """Check if current (or offset day) is holiday.

    Args:
        offset_days: 0 means today, 1 tomorrow, -1 yesterday

    Returns:
        True if desired day is holiday
    """
    day_to_check = datetime.datetime.now() + datetime.timedelta(days=offset_days)
    return day_to_check in _BY_HOLIDAYS
