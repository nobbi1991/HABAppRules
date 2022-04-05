"""Helper for OpenHAB items."""
from __future__ import annotations

import datetime
import typing

import HABApp.core.Items
import HABApp.core.items
import HABApp.openhab.events

_MOCKED_ITEM_NAMES = []


def add_mock_item(item_type: typing.Type[HABApp.openhab.items.OpenhabItem], name: str, initial_value: typing.Union[str, int, float] = None) -> None:
	"""Add a mock item.

	:param item_type: Type of the mock item
	:param name: Name of the mock item
	:param initial_value: initial value
	"""
	if name in HABApp.core.Items._ALL_ITEMS:  # pylint: disable=no-member,protected-access
		HABApp.core.Items.pop_item(name)  # pylint: disable=no-member
	item = item_type(name, initial_value)
	HABApp.core.Items.add_item(item)  # pylint: disable=no-member
	_MOCKED_ITEM_NAMES.append(name)


def remove_mocked_item_by_name(name: str) -> None:
	"""Remove a mocked item by item name

	:param name: name of mocked item
	"""
	HABApp.core.Items.pop_item(name)  # pylint: disable=no-member
	_MOCKED_ITEM_NAMES.remove(name)


def remove_all_mocked_items() -> None:
	"""Remove all mocked items."""
	for name in _MOCKED_ITEM_NAMES:
		HABApp.core.Items.pop_item(name)  # pylint: disable=no-member
	_MOCKED_ITEM_NAMES.clear()


def set_state(item_name: str, value: typing.Any) -> None:
	"""Helper to set state of item.

	:param item_name: name of item
	:param value: state which should be set
	"""
	item = HABApp.openhab.items.OpenhabItem.get_item(item_name)
	item.set_value(value)
	assert_value(item_name, value)


def send_command(item_name: str, new_value: str | datetime.datetime, old_value: str = None) -> None:
	"""Replacement of send_command for unit-tests.

	:param item_name: Name of item
	:param new_value: new value
	:param old_value: previous value
	"""
	set_state(item_name, new_value)
	if old_value:
		HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateChangedEvent(item_name, new_value, 'OFF'))
	else:
		HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateEvent(item_name, new_value))


def assert_value(item_name: str, value: typing.Any, message: typing.Any = None) -> None:
	"""Helper to assert if item has correct state

	:param item_name: name of item
	:param value: expected state
	:param message: message to display if assertion failed
	:raises AssertionError: if value is wrong
	"""
	if (current_state := HABApp.openhab.items.OpenhabItem.get_item(item_name).value) != value:
		msg = f"Wrong state of item '{item_name}'. Expected: {value} | Current: {current_state}"
		if message:
			msg += f'message = {message}'
		raise AssertionError(msg)
