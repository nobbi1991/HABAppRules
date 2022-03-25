import HABApp.core.items
import HABApp.openhab.events


def set_state(item_name, value) -> None:
    """Helper to set state of item.

    :param item_name: name of item
    :param value: state which should be set
    """
    item = HABApp.openhab.items.OpenhabItem.get_item(item_name)
    item.set_value(value)
    assert_state(item_name, value)


def send_command(item_name, new_value, old_value=None):
    set_state(item_name, new_value)
    if old_value:
        HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateChangedEvent(item_name, new_value, 'OFF'))
    else:
        HABApp.core.EventBus.post_event(item_name, HABApp.openhab.events.ItemStateEvent(item_name, new_value))


def assert_state(item_name, value) -> None:
    """Helper to assert if item has correct state

    :param item_name: name of item
    :param value: expected state
    """
    if (current_state := HABApp.openhab.items.OpenhabItem.get_item(item_name).value) != value:
        raise AssertionError(f"Wrong state of item '{item_name}'. Expected: {value} | Current: {current_state}")
