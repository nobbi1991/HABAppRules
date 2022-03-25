"""This is file is written from spacemanspiff2007 and copied from GitHub."""
import os

import HABApp
import HABApp.openhab.connection_handler.func_sync

import definitions


class StateMachineRule(HABApp.Rule):
    states: list[dict] = []
    trans: list[dict] = []
    state: str

    def __init__(self):
        super().__init__()
        self._item_prefix = f"{self.__class__.__mro__[0].__module__}.{self.rule_name}".replace(".", "_")
        self._item_state = self._create_additional_item(f"{self._item_prefix}_state", "String")

    @staticmethod
    def _create_additional_item(name: str, item_type: str) -> HABApp.openhab.items.OpenhabItem:
        """Create additional item if it does not already exists

        :param name: Name of item
        :param item_type: Type of item (e.g. String)
        :return: returns the created item
        """
        if not HABApp.openhab.interface.item_exists(name):
            result = HABApp.openhab.interface.create_item(item_type=item_type, name=name, label=name.replace("_", " "))
        return HABApp.openhab.items.OpenhabItem.get_item(name)

    def _get_initial_state(self, default_value: str) -> str:
        """Get initial state of state machine.

        :param default_value: default / initial state
        :return: if openhab item has a state it will return it, otherwise return the given default value
        """
        if self._item_state.value and self._item_state.value in [item.get("name", None) for item in self.states if isinstance(item, dict)]:
            return self._item_state.value
        return default_value

    def _update_openhab_state(self) -> None:
        """Update openhab state item. This should method should be set to "after_state_change" of the state machine."""
        self._item_state.oh_send_command(self.state)

    @staticmethod
    def _send_if_different(item_name: str, value: str) -> None:
        """

        :param item_name:
        :param value:
        :return:
        """
        if str(HABApp.openhab.items.OpenhabItem.get_item(item_name).value) != value:
            HABApp.openhab.connection_handler.func_sync.send_command(item_name, value)
