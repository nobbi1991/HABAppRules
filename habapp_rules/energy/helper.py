import datetime
import logging

from HABApp.openhab.items import NumberItem

LOGGER = logging.getLogger(__name__)


def get_historic_value(item: NumberItem, start_time: datetime.datetime, default_value: float = 0.0) -> float:
    """Get historic value of given Number item.

    The value is searched in the hour after ``start_time`` first. If no data is found there, the hour before ``start_time`` is searched as a fallback. The backward fallback is required for the start-of-current-month boundary, which is requested at the exact instant it occurs (e.g. the 1st at 00:00:00): at that moment persistence has no future data yet, so a forward-only lookup would wrongly return 0.

    Args:
        item: item instance
        start_time: start time to search for the interested value
        default_value: value which is returned, if no value is found

    Returns:
        historic value of the item
    """
    forward = item.get_persistence_data(start_time=start_time, end_time=start_time + datetime.timedelta(hours=1)).data
    if forward:
        return next((v for v in forward.values() if isinstance(v, float | int)), default_value)

    backward = item.get_persistence_data(start_time=start_time - datetime.timedelta(hours=1), end_time=start_time).data
    if backward:
        return next((v for v in reversed(backward.values()) if isinstance(v, float | int)), default_value)

    LOGGER.warning(f"Could not get value of item '{item.name}' of time = {start_time}")
    return 0
