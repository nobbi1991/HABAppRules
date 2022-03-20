import HABApp.core.items


def set_state(item_name, value) -> None:
    """Helper to set state of item.

    :param item_name: name of item
    :param value: state which should be set
    """
    HABApp.core.Items.get_item(item_name).value = value
    assert_state(item_name, value)


def assert_state(item_name, value) -> None:
    """Helper to assert if item has correct state

    :param item_name: name of item
    :param value: expected state
    """
    if (current_state := HABApp.core.Items.get_item(item_name).value) != value:
        raise AssertionError(f"Wrong state of item '{item_name}'. Expected: {value} | Current: {current_state}")
