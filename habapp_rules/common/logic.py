"""Implementations of logical functions."""
import abc
import logging

import HABApp

import habapp_rules.common.config.logic
import habapp_rules.core.helper
import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class _BinaryLogicBase(HABApp.Rule):
	"""Base class for binary logical functions."""

	def __init__(self, config: habapp_rules.common.config.logic.BinaryLogicConfig) -> None:
		"""Init a logical function.

		:param config: Config for logical function
		:raises TypeError: if unsupported item-type is given for output_name
		"""
		HABApp.Rule.__init__(self)
		self._config = config
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, f"{self.__class__.__name__}_{self._config.items.output.name}")

		if isinstance(self._config.items.output, HABApp.openhab.items.SwitchItem):
			# item type is Switch
			self._positive_state = "ON"
			self._negative_state = "OFF"
		else:
			# item type is Contact (validated by type of config)
			self._positive_state = "CLOSED"
			self._negative_state = "OPEN"

		for item in self._config.items.inputs:
			item.listen_event(self._cb_input_event, HABApp.openhab.events.ItemStateUpdatedEventFilter())

		self._cb_input_event(None)
		input_names = [item.name for item in self._config.items.inputs]
		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with was successful. Output item = '{self._config.items.output.name}' | Input items = '{input_names}'")

	@abc.abstractmethod
	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""

	def _set_output_state(self, output_state: str) -> None:
		"""Set state to the output element

		:param output_state: state which will be set
		"""
		if isinstance(self._config.items.output, HABApp.openhab.items.ContactItem):
			self._config.items.output.oh_post_update(output_state)
		else:
			habapp_rules.core.helper.send_if_different(self._config.items.output, output_state)


class And(_BinaryLogicBase):
	"""Logical AND function.

	Example:
	habapp_rules.common.logic.And(["Item_1", "Item_2"], "Item_result")
	"""

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		output_state = self._positive_state if all(item.value == self._positive_state for item in self._config.items.inputs) else self._negative_state
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
		output_state = self._positive_state if any(item.value == self._positive_state for item in self._config.items.inputs) else self._negative_state
		self._set_output_state(output_state)


class _NumericLogicBase(HABApp.Rule):
	"""Base class for numeric logical functions."""

	def __init__(self, config: habapp_rules.common.config.logic.NumericLogicConfig) -> None:
		"""Init a logical function.

		:param config: Config for logical function
		:raises TypeError: if unsupported item-type is given for output_name
		"""
		HABApp.Rule.__init__(self)
		self._config = config
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, f"{self.__class__.__name__}_{self._config.items.output.name}")

		for item in self._config.items.inputs:
			item.listen_event(self._cb_input_event, HABApp.openhab.events.ItemStateChangedEventFilter())

		self._cb_input_event(None)
		input_names = [item.name for item in self._config.items.inputs]
		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with was successful. Output item = '{self._config.items.output.name}' | Input items = '{input_names}'")

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateUpdatedEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		filtered_items = habapp_rules.core.helper.filter_updated_items(self._config.items.inputs, self._config.parameter.ignore_old_values_time)
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

	def _set_output_state(self, output_state: float) -> None:
		"""Set state to the output element

		:param output_state: state which will be set
		"""
		habapp_rules.core.helper.send_if_different(self._config.items.output, output_state)


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


class Sum(_NumericLogicBase):
	"""Logical Sum function with filter for old / not updated items.

	Example:
	habapp_rules.common.logic.Sum(["Item_1", "Item_2"], "Item_result", 600)
	"""

	def __init__(self, config: habapp_rules.common.config.logic.NumericLogicConfig) -> None:
		"""Init a logical function.

		:param config: config for logical sum rule
		:raises TypeError: if unsupported item-type is given for output_name
		"""
		if isinstance(config.items.output, HABApp.openhab.items.DimmerItem):
			raise TypeError(f"Dimmer items can not be used for Sum function! Given output_name: {config.items.output}")

		_NumericLogicBase.__init__(self, config)

	def _apply_numeric_logic(self, input_values: list[float]) -> float:
		"""Apply numeric logic

		:param input_values: input values
		:return: min value of the given values
		"""
		return sum(val for val in input_values if val is not None)


class InvertValue(HABApp.Rule):
	"""Rule to update another item if the value of an item changed.

	Example:
	habapp_rules.common.logic.InvertValue("Item_1", "Item_2")
	"""

	def __init__(self, config: habapp_rules.common.config.logic.InvertValueConfig) -> None:
		"""Init rule.

		:param config: Config for invert value rule
		"""
		HABApp.Rule.__init__(self)
		self._config = config
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, f"{self.__class__.__name__}_{self._config.items.output.name}")

		self._config.items.input.listen_event(self._cb_input_value, HABApp.openhab.events.ItemStateChangedEventFilter())
		self._cb_input_value(HABApp.openhab.events.ItemStateChangedEvent(self._config.items.input.name, self._config.items.input.value, None))
		self._instance_logger.debug(f"Init of rule '{self.__class__.__name__}' with was successful. Output item = '{self._config.items.output.name}' | Input item = '{self._config.items.input.name}'")

	def _cb_input_value(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Set output, when input value changed

		:param event: event, which triggered this callback
		"""
		if event.value is None:
			return

		output_value = -1 * event.value

		if self._config.parameter.only_negative and output_value > 0:
			output_value = 0
		elif self._config.parameter.only_positive and output_value < 0:
			output_value = 0

		self._config.items.output.oh_send_command(output_value)
