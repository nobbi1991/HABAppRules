"""Base class for Rule with State Machine."""

import HABApp
import HABApp.openhab.connection_handler.func_sync
import transitions.extensions.states


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class StateMachineWithTimeout(transitions.Machine):
	"""State machine class with timeout"""


class StateMachineRule(HABApp.Rule):
	"""Base class for creating rules with a state machine."""
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
			HABApp.openhab.interface.create_item(item_type=item_type, name=name, label=name.replace("_", " "))
		return HABApp.openhab.items.OpenhabItem.get_item(name)

	def _get_initial_state(self, default_value: str) -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		if self._item_state.value and self._item_state.value in [item.get("name", None) for item in self.states if isinstance(item, dict)]:
			return self._item_state.value
		return default_value

	def _update_openhab_state(self) -> None:
		"""Update OpenHAB state item. This should method should be set to "after_state_change" of the state machine."""
		self._item_state.oh_send_command(self.state)
