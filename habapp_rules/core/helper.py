"""Common helper functions for all rules."""
import logging
import time

import HABApp
import HABApp.openhab.connection.handler.func_sync
import HABApp.openhab.items

import habapp_rules.core.exceptions

LOGGER = logging.getLogger(__name__)


def create_additional_item(name: str, item_type: str, label: str | None = None) -> HABApp.openhab.items.OpenhabItem:
	"""Create additional item if it does not already exist

	:param name: Name of item
	:param item_type: Type of item (e.g. String)
	:param label: Label of the item
	:return: returns the created item
	:raises habapp_rules.core.exceptions.HabAppRulesException: if item could not be created
	"""
	name = f"H_{name.removeprefix('H_')}"

	if not HABApp.openhab.interface_sync.item_exists(name):
		if not label:
			label = f"{name.removeprefix('H_').replace('_', ' ')}"
		if item_type == "String" and not label.endswith("[%s]"):
			label = f"{label} [%s]"
		if not HABApp.openhab.interface_sync.create_item(item_type=item_type, name=name, label=label):
			raise habapp_rules.core.exceptions.HabAppRulesException(f"Could not create item '{name}'")
		time.sleep(0.05)
	return HABApp.openhab.items.OpenhabItem.get_item(name)


def send_if_different(item: str | HABApp.openhab.items.OpenhabItem, value: str) -> None:
	"""Send command if the target value is different to the current value.

	:param item: name of OpenHab item
	:param value: value to write to OpenHAB item
	"""
	if isinstance(item, str):
		item = HABApp.openhab.items.OpenhabItem.get_item(item)

	if item.value != value:
		item.oh_send_command(value)


def filter_updated_items(input_items: list[HABApp.openhab.items.OpenhabItem], filter_time: int | None = None) -> list[HABApp.openhab.items.OpenhabItem]:
	"""Get input items depending on their last update time and _ignore_old_values_time

	:param input_items: all items which should be checked for last update time
	:param filter_time: threshold for last update time
	:return: full list if _ignore_old_values is not set, otherwise all items where updated in time.
	"""
	if filter_time is None:
		return input_items

	current_time = time.time()
	filtered_items = [item for item in input_items if current_time - item.last_update.timestamp() <= filter_time]

	if len(input_items) != len(filtered_items):
		ignored_item_names = [item.name for item in input_items if current_time - item.last_update.timestamp() > filter_time]
		LOGGER.warning(f"The following items where not updated during the last {filter_time}s and will be ignored: {ignored_item_names}")

	return filtered_items
