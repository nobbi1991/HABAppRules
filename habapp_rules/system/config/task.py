import datetime
from typing import Self

import pydantic
from HABApp.openhab.items import DatetimeItem, NumberItem, SwitchItem

from habapp_rules.core.helper import create_additional_item
from habapp_rules.core.pydantic_base import ConfigBase, ItemBase, ParameterBase


class RecurringTaskItems(ItemBase):
    """Items for recurring task."""

    task_active: SwitchItem = pydantic.Field(..., description="item which is set to ON if task is active")
    last_done: DatetimeItem = pydantic.Field(None, description="item for date/time when task was last marked as done")  # type: ignore[assignment]  # item will be set in validator if None is given

    @pydantic.model_validator(mode="after")
    def create_additional_items(self) -> Self:
        """Create additional items if they are not set.

        Returns:
            Validated config
        """
        if self.last_done is None:
            self.last_done = create_additional_item(f"H_{self.task_active.name}_last_done", DatetimeItem)

        return self


class RecurringTaskParameter(ParameterBase):
    """Parameter for recurring task."""

    recurrence_time: datetime.timedelta = pydantic.Field(..., description="recurrence time for task. E.g. if it is set to 10 days, the task will be marked as undone 10 days after it was marked as done")
    fixed_check_time: datetime.time | None = pydantic.Field(None, description="fixed time to check if task must set to done. If set to None, the check time will be calculated based on the recurrence time")

    @pydantic.field_validator("recurrence_time")
    @classmethod
    def cycle_must_be_greater_than_12_hours(cls, v: datetime.timedelta) -> datetime.timedelta:
        """Validate that the cycle is greater than 12 hours.

        Args:
            v: given value

        Returns:
            validated value

        Raises:
            ValueError: if cycle is not greater than 12 hours
        """
        if v < datetime.timedelta(hours=12):
            msg = "Cycle must be greater than 12 hours"
            raise ValueError(msg)
        return v


class RecurringTaskConfig(ConfigBase):
    """Config for recurring task."""

    items: RecurringTaskItems = pydantic.Field(..., description="items for time task")
    parameter: RecurringTaskParameter = pydantic.Field(..., description="parameter for time task")


class CounterTaskItems(ItemBase):
    """Items for counter task."""

    task_active: SwitchItem = pydantic.Field(..., description="item which is set to ON if task is active")
    observed: NumberItem = pydantic.Field(..., description="Number item which will be observed")
    last_reset: NumberItem = pydantic.Field(None, description="Item which holds the value of the last reset. If set to None, it will be auto-created")  # type: ignore[assignment]  # item will be set in validator if None is given

    @pydantic.model_validator(mode="after")
    def create_additional_items(self) -> Self:
        """Create additional items if they are not set.

        Returns:
            Validated config
        """
        if self.last_reset is None:
            self.last_reset = create_additional_item(f"H_{self.observed.name}_last_reset", NumberItem)

        return self


class CounterTaskParameter(ParameterBase):
    """Parameter for counter task."""

    max_value: int = pydantic.Field(..., description="value, after which the task will be set to active")


class CounterTaskConfig(ConfigBase):
    """Config for counter task."""

    items: CounterTaskItems = pydantic.Field(..., description="items for counter task")
    parameter: CounterTaskParameter = pydantic.Field(..., description="parameter for counter task")
