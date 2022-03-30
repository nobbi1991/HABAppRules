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
    if name in HABApp.core.Items._ALL_ITEMS:
        HABApp.core.Items.pop_item(name)
    item = item_type(name, initial_value)
    HABApp.core.Items.add_item(item)
    _MOCKED_ITEM_NAMES.append(name)


def remove_moved_items() -> None:
    """Remove all mocked items."""
    for name in _MOCKED_ITEM_NAMES:
        HABApp.core.Items.pop_item(name)
    _MOCKED_ITEM_NAMES.clear()


def set_state(item_name, value) -> None:
    """Helper to set state of item.

    :param item_name: name of item
    :param value: state which should be set
    """
    item = HABApp.openhab.items.OpenhabItem.get_item(item_name)
    item.set_value(value)
    assert_value(item_name, value)


def send_command(item_name, new_value, old_value=None):
    set_state(item_name, new_value)
    if old_value:
        HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateChangedEvent(item_name, new_value, 'OFF'))
    else:
        HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateEvent(item_name, new_value))


def assert_value(item_name, value) -> None:
    """Helper to assert if item has correct state

    :param item_name: name of item
    :param value: expected state
    """
    if (current_state := HABApp.openhab.items.OpenhabItem.get_item(item_name).value) != value:
        raise AssertionError(f"Wrong state of item '{item_name}'. Expected: {value} | Current: {current_state}")
