"""Common helper functions for all rules."""

import logging
import time

import HABApp.openhab.items

import habapp_rules.core.exceptions

LOGGER = logging.getLogger(__name__)


def create_additional_item(name: str, item_type: str, label: str | None = None, groups: list[str] | None = None) -> HABApp.openhab.items.OpenhabItem:
    """Create additional item if it does not already exist.

    Args:
        name: Name of item
        item_type: Type of item (e.g. String)
        label: Label of the item
        groups: in which groups is the item

    Returns:
        returns the created item

    Raises:
        habapp_rules.core.exceptions.HabAppRulesError: if item could not be created
    """
    if not name.startswith("H_"):
        LOGGER.warning(f"Item '{name}' does not start with 'H_'. All automatically created items must start with 'H_'. habapp_rules will add 'H_' automatically.")
        name = f"H_{name}"

    if not HABApp.openhab.interface_sync.item_exists(name):
        if not label:
            label = f"{name.removeprefix('H_').replace('_', ' ')}"
        if not HABApp.openhab.interface_sync.create_item(item_type=item_type, name=name, label=label, groups=groups):
            msg = f"Could not create item '{name}'"
            raise habapp_rules.core.exceptions.HabAppRulesError(msg)
        time.sleep(0.05)
    return HABApp.openhab.items.OpenhabItem.get_item(name)


def send_if_different(item: str | HABApp.openhab.items.OpenhabItem, value: str | float) -> None:
    """Send command if the target value is different to the current value.

    Args:
        item: name of OpenHab item
        value: value to write to OpenHAB item
    """
    if isinstance(item, str):
        item = HABApp.openhab.items.OpenhabItem.get_item(item)

    if item.value != value:
        item.oh_send_command(value)


def filter_updated_items(input_items: list[HABApp.openhab.items.OpenhabItem], filter_time: int | None = None) -> list[HABApp.openhab.items.OpenhabItem]:
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
