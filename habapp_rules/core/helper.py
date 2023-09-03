"""Common helper functions for all rules."""

import time

import HABApp.openhab.connection.handler.func_sync
import HABApp.openhab.items

import habapp_rules.core.exceptions


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


def send_if_different(item_name: str, value: str) -> None:
	"""Send command if the target value is different to the current value.

	:param item_name: name of OpenHab item
	:param value: value to write to OpenHAB item
	"""
	if str(HABApp.openhab.items.OpenhabItem.get_item(item_name).value) != value:
		HABApp.openhab.items.OpenhabItem.get_item(item_name).oh_send_command(value)
