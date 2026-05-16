import datetime
import logging

from HABApp.openhab.items import NumberItem

LOGGER = logging.getLogger(__name__)


def get_historic_value(item: NumberItem, start_time: datetime.datetime, default_value: float = 0.0) -> float:
    """Get historic value of given Number item.

    Args:
        item: item instance
        start_time: start time to search for the interested value
        default_value: value which is returned, if no value is found

    Returns:
        historic value of the item
    """
    historic = item.get_persistence_data(start_time=start_time, end_time=start_time + datetime.timedelta(hours=1)).data
    if not historic:
        LOGGER.warning(f"Could not get value of item '{item.name}' of time = {start_time}")
        return 0

    return next((v for v in historic.values() if isinstance(v, float | int)), default_value)
