"""Implementations of logical functions."""

import abc
from typing import cast

from HABApp.openhab.events import ItemStateChangedEvent, ItemStateUpdatedEvent
from HABApp.openhab.events.event_filters import ItemStateChangedEventFilter, ItemStateUpdatedEventFilter
from HABApp.openhab.items import ContactItem, DimmerItem, SwitchItem
from HABApp.util.functions.min_max import max as habapp_max
from HABApp.util.functions.min_max import min as habapp_min

from habapp_rules.common.config.logic import BinaryLogicConfig, InvertValueConfig, NumericLogicConfig
from habapp_rules.core.base import RuleBase
from habapp_rules.core.helper import filter_updated_items, send_if_different


class _BinaryLogicBase(RuleBase):
    """Base class for binary logical functions."""

    def __init__(self, config: BinaryLogicConfig) -> None:
        """Init a logical function.

        Args:
            config: Config for logical function

        Raises:
            TypeError: if unsupported item-type is given for output_name
        """
        self._config = config
        RuleBase.__init__(self, self._config.items.output.name)

        if isinstance(self._config.items.output, SwitchItem):
            # item type is Switch
            self._positive_state = "ON"
            self._negative_state = "OFF"
        else:
            # item type is Contact (validated by type of config)
            self._positive_state = "CLOSED"
            self._negative_state = "OPEN"

        for item in self._config.items.inputs:
            item.listen_event(self._cb_input_event, ItemStateUpdatedEventFilter())

        self._cb_input_event(None)
        input_names = [item.name for item in self._config.items.inputs]
        self._log_init_done(f"Output item = '{self._config.items.output.name}' | Input items = {input_names}")

    @abc.abstractmethod
    def _cb_input_event(self, event: ItemStateUpdatedEvent | None) -> None:
        """Callback, which is called if one of the input items had a state event.

        Args:
            event: item event of the updated item
        """

    def _set_output_state(self, output_state: str) -> None:
        """Set state to the output element.

        Args:
            output_state: state which will be set
        """
        if isinstance(self._config.items.output, ContactItem):
            self._config.items.output.oh_post_update(output_state)
        else:
            send_if_different(self._config.items.output, output_state)


class And(_BinaryLogicBase):
    """Logical AND function.

    # Config:
    config = BinaryLogicConfig(
            items=BinaryLogicItems(
                    inputs=["Item_1", "Item_2"],
                    output="Item_result",
            )
    )

    # Rule init:
    And(config)
    """

    def _cb_input_event(self, _: ItemStateUpdatedEvent | None) -> None:
        """Callback, which is called if one of the input items had a state event."""
        output_state = self._positive_state if all(item.value == self._positive_state for item in self._config.items.inputs) else self._negative_state
        self._set_output_state(output_state)


class Or(_BinaryLogicBase):
    """Logical OR function.

    # Config:
    config = BinaryLogicConfig(
            items=BinaryLogicItems(
                    inputs=["Item_1", "Item_2"],
                    output="Item_result",
            )
    )

    # Rule init:
    Or(config)
    """

    def _cb_input_event(self, _: ItemStateUpdatedEvent | None) -> None:
        """Callback, which is called if one of the input items had a state event."""
        output_state = self._positive_state if any(item.value == self._positive_state for item in self._config.items.inputs) else self._negative_state
        self._set_output_state(output_state)


class _NumericLogicBase(RuleBase):
    """Base class for numeric logical functions."""

    def __init__(self, config: NumericLogicConfig) -> None:
        """Init a logical function.

        Args:
            config: Config for logical function

        Raises:
            TypeError: if unsupported item-type is given for output_name
        """
        self._config = config
        RuleBase.__init__(self, self._config.items.output.name)

        for item in self._config.items.inputs:
            item.listen_event(self._cb_input_event, ItemStateChangedEventFilter())

        self._cb_input_event(None)
        input_names = [item.name for item in self._config.items.inputs]
        self._log_init_done(f"Output item = '{self._config.items.output.name}' | Input items = {input_names}")

    def _cb_input_event(self, _: ItemStateUpdatedEvent | None) -> None:
        """Callback, which is called if one of the input items had a state event."""
        filtered_items = filter_updated_items(self._config.items.inputs, self._config.parameter.ignore_old_values_time)
        value = self._apply_numeric_logic([item.value for item in filtered_items if item is not None])

        if value is None:
            return

        self._set_output_state(value)

    @staticmethod
    @abc.abstractmethod
    def _apply_numeric_logic(input_values: list[float]) -> float:
        """Apply numeric logic.

        Args:
            input_values: input values

        Returns:
            value which fulfills the filter type
        """

    def _set_output_state(self, output_state: float) -> None:
        """Set state to the output element.

        Args:
            output_state: state which will be set
        """
        send_if_different(self._config.items.output, output_state)


class Min(_NumericLogicBase):
    """Logical Min function with filter for old / not updated items.

    # Config:
    config = NumericLogicConfig(
            items=NumericLogicItems(
                    inputs=["Item_1", "Item_2"],
                    output="Item_result",
            ),
            parameter=NumericLogicParameter(
                    ignore_old_values_time=600
            ),
    )

    # Rule init:
    Min(config)
    """

    @staticmethod
    def _apply_numeric_logic(input_values: list[float]) -> float:
        """Apply numeric logic.

        Args:
            input_values: input values

        Returns:
            min value of the given values
        """
        return cast("float", habapp_min(input_values))


class Max(_NumericLogicBase):
    """Logical Max function with filter for old / not updated items.

    # Config:
    config = NumericLogicConfig(
            items=NumericLogicItems(
                    inputs=["Item_1", "Item_2"],
                    output="Item_result",
            ),
            parameter=NumericLogicParameter(
                    ignore_old_values_time=600
            ),
    )

    # Rule init:
    Max(config)
    """

    @staticmethod
    def _apply_numeric_logic(input_values: list[float]) -> float:
        """Apply numeric logic.

        Args:
            input_values: input values

        Returns:
            max value of the given values
        """
        return cast("float", habapp_max(input_values))


class Sum(_NumericLogicBase):
    """Logical Sum function with filter for old / not updated items.

    # Config:
    config = NumericLogicConfig(
            items=NumericLogicItems(
                    inputs=["Item_1", "Item_2"],
                    output="Item_result",
            ),
            parameter=NumericLogicParameter(
                    ignore_old_values_time=600
            ),
    )

    # Rule init:
    Sum(config)
    """

    def __init__(self, config: NumericLogicConfig) -> None:
        """Init a logical function.

        Args:
            config: config for logical sum rule

        Raises:
            TypeError: if unsupported item-type is given for output_name
        """
        if isinstance(config.items.output, DimmerItem):
            msg = f"Dimmer items can not be used for Sum function! Given output_name: {config.items.output}"
            raise TypeError(msg)

        _NumericLogicBase.__init__(self, config)

    @staticmethod
    def _apply_numeric_logic(input_values: list[float]) -> float:
        """Apply numeric logic.

        Args:
            input_values: input values

        Returns:
            min value of the given values
        """
        return sum(val for val in input_values if val is not None)


class InvertValue(RuleBase):
    """Rule to update another item if the value of an item changed.

    # Config:
    config = InvertValueConfig(
            items= InvertValueItems(
                    input="Item_1",
                    output="Item_2",
            )
    )

    # Rule init:
    InvertValue(config)
    """

    def __init__(self, config: InvertValueConfig) -> None:
        """Init rule.

        Args:
            config: Config for invert value rule
        """
        self._config = config
        RuleBase.__init__(self, self._config.items.output.name)

        self._config.items.input.listen_event(self._cb_input_value, ItemStateChangedEventFilter())
        self._cb_input_value(ItemStateChangedEvent(self._config.items.input.name, self._config.items.input.value, None))
        self._log_init_done(f"Output item = '{self._config.items.output.name}' | Input item = '{self._config.items.input.name}'")

    def _cb_input_value(self, event: ItemStateChangedEvent) -> None:
        """Set output, when input value changed.

        Args:
            event: event, which triggered this callback
        """
        if event.value is None:
            return

        output_value = -1 * event.value

        if (self._config.parameter.only_negative and output_value > 0) or (self._config.parameter.only_positive and output_value < 0):
            output_value = 0

        self._config.items.output.oh_send_command(output_value)
