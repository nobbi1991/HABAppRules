"""Base class for Rule with State Machine."""
import inspect
import os
import pathlib
import time

import HABApp
import HABApp.openhab.connection_handler.func_sync
import transitions.extensions.states

import habapp_rules


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class StateMachineWithTimeout(transitions.Machine):
	"""State machine class with timeout"""


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class HierarchicalStateMachineWithTimeout(transitions.extensions.HierarchicalMachine):
	"""Hierarchical state machine class with timeout"""


class StateMachineRule(HABApp.Rule):
	"""Base class for creating rules with a state machine."""
	states: list[dict] = []
	trans: list[dict] = []
	state: str

	def __init__(self, state_item_name: str | None = None, state_item_label: str | None = None):
		"""Init rule with state machine.

		:param state_item_name: name of the item to hold the state
		:param state_item_label: OpenHAB label of the state_item; This will be used if the state_item will be created by HABApp
		"""
		super().__init__()

		# get prefix for items
		parent_class_path = pathlib.Path(inspect.getfile(self.__class__.__mro__[0]))
		parent_class_path_relative = parent_class_path.relative_to(habapp_rules.BASE_PATH)
		parent_class_path_relative_str = str(parent_class_path_relative).removesuffix(".py").replace(os.path.sep, "_")
		self._item_prefix = f"{parent_class_path_relative_str}.{self.rule_name}".replace(".", "_")

		if not state_item_name:
			state_item_name = f"{self._item_prefix}_state"
		self._item_state = self._create_additional_item(state_item_name, "String", state_item_label)

	@staticmethod
	def _create_additional_item(name: str, item_type: str, label: str | None = None) -> HABApp.openhab.items.OpenhabItem:
		"""Create additional item if it does not already exist

		:param name: Name of item
		:param item_type: Type of item (e.g. String)
		:param label: Label of the item
		:return: returns the created item
		"""
		if not HABApp.openhab.interface.item_exists(name):
			if not label:
				label = f"{name.replace('_', ' ')}"
			if item_type == "String" and not label.endswith("[%s]"):
				label = f"{label} [%s]"
			HABApp.openhab.interface.create_item(item_type=item_type, name=name, label=label)
		time.sleep(0.05)
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
