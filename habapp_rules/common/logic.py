"""Implementations of logical functions."""
import abc
import logging
import time

import HABApp

import habapp_rules.core.helper
import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class _BinaryLogicBase(HABApp.Rule):
	"""Base class for binary logical functions."""

	def __init__(self, input_names: list[str], output_name: str) -> None:
		"""Init a logical function.

		:param input_names: list of input items (must be either Switch or Contact and all have to match to output_item)
		:param output_name: name of output item
		:raises TypeError: if unsupported item-type is given for output_name
		"""
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, f"{self.__class__.__name__}_{output_name}")

		self._output_item = HABApp.openhab.items.OpenhabItem.get_item(output_name)

		if isinstance(self._output_item, HABApp.openhab.items.SwitchItem):
			self._positive_state = "ON"
			self._negative_state = "OFF"
		elif isinstance(self._output_item, HABApp.openhab.items.ContactItem):
			self._positive_state = "CLOSED"
			self._negative_state = "OPEN"
		else:
			raise TypeError(f"Item type '{type(self._output_item)}' is not supported. Type must be SwitchItem or ContactItem")

		self._input_items = []
		for name in input_names:
			if isinstance(input_item := HABApp.openhab.items.OpenhabItem.get_item(name), type(self._output_item)):
				self._input_items.append(input_item)
				input_item.listen_event(self._cb_input_event, HABApp.openhab.events.ItemStateUpdatedEventFilter())
			else:
				self._instance_logger.error(f"Item '{name}' must have the same type like the output item. Expected: {type(self._output_item)} | actual : {type(input_item)}")

		self._cb_input_event(None)
		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with was successful. Output item = '{output_name}' | Input items = '{input_names}'")

	@abc.abstractmethod
	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""

	def _set_output_state(self, output_state: str) -> None:
		"""Set state to the output element

		:param output_state: state which will be set
		"""
		if isinstance(self._output_item, HABApp.openhab.items.ContactItem):
			self._output_item.oh_post_update(output_state)
		else:
			habapp_rules.core.helper.send_if_different(self._output_item.name, output_state)


class And(_BinaryLogicBase):
	"""Logical AND function.

	Example:
	habapp_rules.common.logic.And(["Item_1", "Item_2"], "Item_result")
	"""

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		output_state = self._positive_state if all(item.value == self._positive_state for item in self._input_items) else self._negative_state
		self._set_output_state(output_state)


class Or(_BinaryLogicBase):
	"""Logical OR function.

	Example:
	habapp_rules.common.logic.Or(["Item_1", "Item_2"], "Item_result")
	"""

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		output_state = self._positive_state if any(item.value == self._positive_state for item in self._input_items) else self._negative_state
		self._set_output_state(output_state)


class _NumericLogicBase(HABApp.Rule):
	"""Base class for numeric logical functions."""

	def __init__(self, input_names: list[str], output_name: str, ignore_old_values_time: int | None = None) -> None:
		"""Init a logical function.

		:param input_names: list of input items (must be either Dimmer or Number and all have to match to output_item)
		:param output_name: name of output item
		:param ignore_old_values_time: ignores values which are older than the given time in seconds. If None, all values will be taken
		:raises TypeError: if unsupported item-type is given for output_name
		"""
		self._ignore_old_values_time = ignore_old_values_time

		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, f"{self.__class__.__name__}_{output_name}")

		self._output_item = HABApp.openhab.items.OpenhabItem.get_item(output_name)

		if not isinstance(self._output_item, (HABApp.openhab.items.DimmerItem, HABApp.openhab.items.NumberItem)):
			raise TypeError(f"Item type '{type(self._output_item)}' is not supported. Type must be NumberItem or DimmerItem")

		self._input_items = []
		for name in input_names:
			if isinstance(input_item := HABApp.openhab.items.OpenhabItem.get_item(name), type(self._output_item)):
				self._input_items.append(input_item)
				input_item.listen_event(self._cb_input_event, HABApp.openhab.events.ItemStateChangedEventFilter())
			else:
				self._instance_logger.error(f"Item '{name}' must have the same type like the output item. Expected: {type(self._output_item)} | actual : {type(input_item)}")

		self._cb_input_event(None)
		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with was successful. Output item = '{output_name}' | Input items = '{input_names}'")

	@abc.abstractmethod
	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""

	def _get_input_items(self) -> list[HABApp.openhab.items.DimmerItem | HABApp.openhab.items.NumberItem]:
		"""Get input items depending on their last update time and _ignore_old_values_time

		:return: full list if _ignore_old_values is not set, otherwise all items where updated in time.
		"""
		if self._ignore_old_values_time is None:
			return self._input_items

		current_time = time.time()
		filtered_items = [item for item in self._input_items if current_time - item.last_update.timestamp() <= self._ignore_old_values_time]

		if len(self._input_items) != len(filtered_items):
			ignored_item_names = [item.name for item in self._input_items if current_time - item.last_update.timestamp() > self._ignore_old_values_time]
			self._instance_logger.warning(f"The following items where not updated during the last {self._ignore_old_values_time}s and will be ignored: {ignored_item_names}")

		return filtered_items

	def _set_output_state(self, output_state: str) -> None:
		"""Set state to the output element

		:param output_state: state which will be set
		"""
		habapp_rules.core.helper.send_if_different(self._output_item.name, output_state)


class Min(_NumericLogicBase):
	"""Logical Min function with filter for old / not updated items.

	Example:
	habapp_rules.common.logic.Min(["Item_1", "Item_2"], "Item_result", 600)
	"""

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		min_item = HABApp.util.functions.min(self._get_input_items())
		if isinstance(min_item, HABApp.openhab.items.OpenhabItem):
			self._set_output_state(min_item.value)


class Max(_NumericLogicBase):
	"""Logical Max function with filter for old / not updated items.

	Example:
	habapp_rules.common.logic.Max(["Item_1", "Item_2"], "Item_result", 600)
	"""

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		max_item = HABApp.util.functions.max(self._get_input_items())
		if isinstance(max_item, HABApp.openhab.items.OpenhabItem):
			self._set_output_state(max_item.value)
