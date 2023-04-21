"""Base class for Rule with State Machine."""
import inspect
import os
import pathlib
import time

import HABApp
import HABApp.openhab.connection_handler.func_sync
import transitions.extensions.states

import habapp_rules
import habapp_rules.core.exceptions


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

	def __init__(self, state_item_name: str | None = None, state_item_label: str | None = None):  # add possibility to give icon
		"""Init rule with state machine.

		:param state_item_name: name of the item to hold the state
		:param state_item_label: OpenHAB label of the state_item; This will be used if the state_item will be created by HABApp
		"""
		HABApp.Rule.__init__(self)

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
		:raises habapp_rules.core.exceptions.HabAppRulesException: if item could not be created
		"""
		if not HABApp.openhab.interface.item_exists(name):
			if not label:
				label = f"{name.replace('_', ' ')}"
			if item_type == "String" and not label.endswith("[%s]"):
				label = f"{label} [%s]"
			if not HABApp.openhab.interface.create_item(item_type=item_type, name=name, label=label):
				raise habapp_rules.core.exceptions.HabAppRulesException(f"Could not create item '{name}'")
			time.sleep(0.05)
		return HABApp.openhab.items.OpenhabItem.get_item(name)

	def get_initial_log_message(self) -> str:
		"""Get log message which can be logged at the init of a rule with a state machine.

		:return: log message
		"""
		return f"Init of rule '{self.__class__.__name__}' with name '{self.rule_name}' was successful. Initial state = '{self.state}' | State item = '{self._item_state.name}'"

	def _get_initial_state(self, default_value: str = "initial") -> str:
		"""Get initial state of state machine.

		:param default_value: default / initial state
		:return: if OpenHAB item has a state it will return it, otherwise return the given default value
		"""
		if self._item_state.value and self._item_state.value in [item.get("name", None) for item in self.states if isinstance(item, dict)]:
			return self._item_state.value
		return default_value

	def _set_initial_state(self) -> None:
		"""Set initial state.
		if the ``initial_state`` parameter of the state machine constructor is used the timeouts will not be started for the initial state.
		"""
		initial_state = self._get_initial_state()
		eval(f"self.to_{initial_state}()")  # pylint: disable=eval-used

	def _update_openhab_state(self) -> None:
		"""Update OpenHAB state item. This should method should be set to "after_state_change" of the state machine."""
		self._item_state.oh_send_command(self.state)
