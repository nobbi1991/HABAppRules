"""Common helper functions for all rules."""

import logging
import time
from typing import TypeVar

from HABApp.openhab.connection.handler.func_sync import create_item, item_exists
from HABApp.openhab.items import CallItem, ColorItem, ContactItem, DatetimeItem, DimmerItem, GroupItem, ImageItem, LocationItem, NumberItem, OpenhabItem, PlayerItem, RollershutterItem, StringItem, SwitchItem

from habapp_rules.core.exceptions import HabAppRulesError

LOGGER = logging.getLogger(__name__)
OH_ITEM_TYPE = TypeVar("OH_ITEM_TYPE", CallItem, ColorItem, ContactItem, DatetimeItem, DimmerItem, GroupItem, ImageItem, LocationItem, NumberItem, OpenhabItem, PlayerItem, RollershutterItem, StringItem, SwitchItem)


def create_additional_item(name: str, item_class: type[OH_ITEM_TYPE], label: str | None = None, groups: list[str] | None = None) -> OH_ITEM_TYPE:
    """Create additional item if it does not already exist.

    Args:
        name: Name of item
        item_class: Class of item (e.g. StringItem)
        label: Label of the item
        groups: in which groups is the item

    Returns:
        returns the created item

    Raises:
        HabAppRulesError: if item could not be created
    """
    if not name.startswith("H_"):
        LOGGER.warning(f"Item '{name}' does not start with 'H_'. All automatically created items must start with 'H_'. habapp_rules will add 'H_' automatically.")
        name = f"H_{name}"

    if not item_exists(name):
        if not label:
            label = f"{name.removeprefix('H_').replace('_', ' ')}"
        if not create_item(item_type=item_class.__name__.removesuffix("Item"), name=name, label=label, groups=groups):
            msg = f"Could not create item '{name}'"
            raise HabAppRulesError(msg)
        time.sleep(0.05)
    return item_class.get_item(name)


def send_if_different(item: str | OpenhabItem, value: str | float) -> None:
    """Send command if the target value is different to the current value.

    Args:
        item: name of OpenHab item
        value: value to write to OpenHAB item
    """
    if isinstance(item, str):
        item = OpenhabItem.get_item(item)

    if item.value != value:
        item.oh_send_command(value)


def filter_updated_items(input_items: list[OH_ITEM_TYPE], filter_time: int | None = None) -> list[OH_ITEM_TYPE]:
    """Get input items depending on their last update time and _ignore_old_values_time.

    Args:
        input_items: all items which should be checked for last update time
        filter_time: threshold for last update time

    Returns:
        full list if _ignore_old_values is not set, otherwise all items where updated in time.
    """
    if filter_time is None:
        return input_items

    filtered_items = [item for item in input_items if item.last_update.newer_than(filter_time)]

    if len(input_items) != len(filtered_items):
        ignored_item_names = [item.name for item in input_items if item.last_update.older_than(filter_time)]
        LOGGER.warning(f"The following items where not updated during the last {filter_time}s and will be ignored: {ignored_item_names}")

    return filtered_items
