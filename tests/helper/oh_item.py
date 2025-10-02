"""Helper for OpenHAB items."""

from __future__ import annotations

import contextlib
import datetime
from typing import TYPE_CHECKING

import HABApp.core
import HABApp.openhab.events

if TYPE_CHECKING:
    from HABApp.openhab.definitions import ThingStatusEnum
    from HABApp.openhab.items import OpenhabItem

NO_VALUE = object()
_MOCKED_ITEM_NAMES = []
StateTypes = str | float | datetime.datetime


def add_mock_item(item_type: type[HABApp.openhab.items.OpenhabItem], name: str, initial_value: str | float | None = None) -> None:
    """Add a mock item.

    Args:
        item_type: Type of the mock item
        name: Name of the mock item
        initial_value: initial value
    """
    if HABApp.core.Items.item_exists(name):
        HABApp.core.Items.pop_item(name)
    item = item_type(name, initial_value)
    HABApp.core.Items.add_item(item)
    _MOCKED_ITEM_NAMES.append(name)


def add_mock_thing(name: str) -> None:
    """Add a mock thing.

    Args:
        name: name of thing
    """
    thing = HABApp.openhab.items.Thing(name)
    HABApp.core.Items.add_item(thing)
    _MOCKED_ITEM_NAMES.append(name)


def remove_mocked_item_by_name(name: str) -> None:
    """Remove a mocked item by item name.

    Args:
        name: name of mocked item
    """
    HABApp.core.Items.pop_item(name)
    _MOCKED_ITEM_NAMES.remove(name)


def remove_all_mocked_items() -> None:
    """Remove all mocked items."""
    for name in _MOCKED_ITEM_NAMES:
        HABApp.core.Items.pop_item(name)
    _MOCKED_ITEM_NAMES.clear()


def set_state(item_name: str, value: StateTypes | None) -> None:
    """Helper to set state of item.

    Args:
        item_name: name of item
        value: state which should be set
    """
    item = HABApp.openhab.items.OpenhabItem.get_item(item_name)
    if isinstance(item, HABApp.openhab.items.DimmerItem) and value in {"ON", "OFF"}:
        value = 100 if value == "ON" else 0

    with contextlib.suppress(AssertionError):
        item.set_value(value)


def set_thing_state(thing_name: str, value: ThingStatusEnum | None) -> None:
    """Helper to set state of thing.

    Args:
        thing_name: name of thing
        value: state which should be set
    """
    thing = HABApp.openhab.items.Thing.get_item(thing_name)
    thing.status = value


def send_command(item_name: str, new_value: StateTypes, old_value: StateTypes = NO_VALUE) -> None:
    """Replacement of send_command for unit-tests.

    Args:
        item_name: Name of item
        new_value: new value
        old_value: previous value
    """
    old_value = HABApp.openhab.items.OpenhabItem.get_item(item_name).value if old_value is NO_VALUE else old_value

    set_state(item_name, new_value)
    if old_value is not NO_VALUE and old_value != new_value:
        HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateChangedEvent(item_name, new_value, old_value))
    HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateUpdatedEvent(item_name, new_value))


def oh_send_command(item: OpenhabItem, new_value: StateTypes, old_value: StateTypes = NO_VALUE) -> None:
    """Replacement of send_command for unit-tests.

    Args:
        item: item
        new_value: new value
        old_value: previous value
    """
    send_command(item.name, new_value, old_value)


def oh_post_update(item: OpenhabItem, new_value: StateTypes) -> None:
    """Replacement of post_update for unit-tests.

    Args:
        item: item
        new_value: new value
    """
    set_state(item.name, new_value)


def item_command_event(item_name: str, value: StateTypes) -> None:
    """Post a command event to the event bus.

    Args:
        item_name: name of item
        value: value of the event
    """
    with contextlib.suppress(HABApp.core.errors.InvalidItemValueError):
        set_state(item_name, value)
    HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemCommandEvent(item_name, value))


def item_state_event(item_name: str, value: StateTypes) -> None:
    """Post a state event to the event bus.

    Args:
        item_name: name of item
        value: value of the event
    """
    set_state(item_name, value)
    HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateUpdatedEvent(item_name, value))


def item_state_change_event(item_name: str, value: StateTypes, old_value: StateTypes = None) -> None:
    """Post a state change event to the event bus.

    Args:
        item_name: name of item
        value: value of the event
        old_value: previous value
    """
    prev_value = old_value or HABApp.openhab.items.OpenhabItem.get_item(item_name).value
    set_state(item_name, value)
    HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateChangedEvent(item_name, value, prev_value))


def thing_status_info_changed_event(thing_name: str, status: ThingStatusEnum) -> None:
    """Trigger a thing status info changed event.

    Args:
        thing_name: name of thing
        status: status
    """
    set_thing_state(thing_name, status)
    HABApp.core.EventBus.post_event(thing_name, HABApp.openhab.events.ThingStatusInfoChangedEvent(thing_name, status))


def assert_value(item_name: str, value: StateTypes | None, message: str | None = None) -> None:
    """Helper to assert if item has correct state.

    Args:
        item_name: name of item
        value: expected state
        message: message to display if assertion failed

    Raises:
        AssertionError: if value is wrong
    """
    if (current_state := HABApp.openhab.items.OpenhabItem.get_item(item_name).value) != value:
        msg = f"Wrong state of item '{item_name}'. Expected: {value} | Current: {current_state}"
        if message:
            msg += f"message = {message}"
        raise AssertionError(msg)
