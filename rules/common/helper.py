"""Common helper functions for all rules."""

import HABApp.openhab.items


def send_if_different(item_name: str, value: str) -> None:
	"""Send command if the target value is different to the current value.

	:param item_name: name of OpenHab item
	:param value: value to write to OpenHAB item
	"""
	if str(HABApp.openhab.items.OpenhabItem.get_item(item_name).value) != value:
		HABApp.openhab.items.OpenhabItem.get_item(item_name).oh_send_command(value)
