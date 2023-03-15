"""Implementations of logical functions."""
import abc
import logging

import HABApp

import habapp_rules.core.helper
import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class _Base(HABApp.Rule):
	"""Base class for logical functions."""

	def __init__(self, input_names: list[str], output_name: str) -> None:
		"""Init a logical function.

		:param input_names: list of input items (must be either Switch or Contact and all have to match to output_item)
		:param output_name: name of output item
		:raises TypeError: if unsupported item-type is given for output_name
		"""
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, output_name)

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
				input_item.listen_event(self._cb_input_event, HABApp.openhab.events.ItemStateEventFilter())
			else:
				self._instance_logger.error(f"Item '{name}' must have the same type like the output item. Expected: {type(self._output_item)} | actual : {type(input_item)}")

		self._cb_input_event(None)

	@abc.abstractmethod
	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""

	def _set_output_sate(self, output_state: str) -> None:
		"""Set state to the output element

		:param output_state: state which will be set
		"""
		if isinstance(self._output_item, HABApp.openhab.items.ContactItem):
			self._output_item.oh_post_update(output_state)
		else:
			habapp_rules.core.helper.send_if_different(self._output_item.name, output_state)


class And(_Base):
	"""Logical AND function."""

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		output_state = self._positive_state if all(item.value == self._positive_state for item in self._input_items) else self._negative_state
		self._set_output_sate(output_state)


class Or(_Base):
	"""Logical OR function."""

	def _cb_input_event(self, event: HABApp.openhab.events.ItemStateEvent | None) -> None:
		"""Callback, which is called if one of the input items had a state event.

		:param event: item event of the updated item
		"""
		output_state = self._positive_state if any(item.value == self._positive_state for item in self._input_items) else self._negative_state
		self._set_output_sate(output_state)
