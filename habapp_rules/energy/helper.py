import datetime
import logging

import HABApp

LOGGER = logging.getLogger(__name__)


def get_historic_value(item: HABApp.openhab.items.NumberItem, start_time: datetime.datetime) -> float:
    """Get historic value of given Number item.

    Args:
        item: item instance
        start_time: start time to search for the interested value

    Returns:
        historic value of the item
    """
    historic = item.get_persistence_data(start_time=start_time, end_time=start_time + datetime.timedelta(hours=1)).data
    if not historic:
        LOGGER.warning(f"Could not get value of item '{item.name}' of time = {start_time}")
        return 0

    return next(iter(historic.values()))
