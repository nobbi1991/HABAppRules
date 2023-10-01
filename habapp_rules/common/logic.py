"""Implementations of logical functions."""
import abc
import logging

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

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		filtered_items = habapp_rules.core.helper.filter_updated_items(self._input_items, self._ignore_old_values_time)
		value = self._apply_numeric_logic([item.value for item in filtered_items if item is not None])

		if value is None:
			return

		self._set_output_state(value)

	@abc.abstractmethod
	def _apply_numeric_logic(self, input_values: list[float]) -> float:
		"""Apply numeric logic

		:param input_values: input values
		:return: value which fulfills the filter type
		"""

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

	def _apply_numeric_logic(self, input_values: list[float]) -> float:
		"""Apply numeric logic

		:param input_values: input values
		:return: min value of the given values
		"""
		return HABApp.util.functions.min(input_values)



class Max(_NumericLogicBase):
	"""Logical Max function with filter for old / not updated items.

	Example:
	habapp_rules.common.logic.Max(["Item_1", "Item_2"], "Item_result", 600)
	"""

	def _apply_numeric_logic(self, input_values: list[float]) -> float:
		"""Apply numeric logic

		:param input_values: input values
		:return: max value of the given values
		"""
		return HABApp.util.functions.max(input_values)
