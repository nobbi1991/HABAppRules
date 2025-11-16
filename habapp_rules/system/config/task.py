import datetime

import HABApp.openhab.items
import pydantic

import habapp_rules.core.pydantic_base


class RecurringTaskItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for recurring task."""

    task_active: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which is set to ON if task is active")
    last_done: HABApp.openhab.items.DatetimeItem | None = pydantic.Field(None, description="item for date/time when task was last marked as done")


class RecurringTaskParameter(habapp_rules.core.pydantic_base.ParameterBase):
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


class RecurringTaskConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for recurring task."""

    items: RecurringTaskItems = pydantic.Field(..., description="items for time task")
    parameter: RecurringTaskParameter = pydantic.Field(..., description="parameter for time task")


class CounterTaskItems(habapp_rules.core.pydantic_base.ItemBase):
    """Items for counter task."""

    task_active: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="item which is set to ON if task is active")
    observed: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="Number item which will be observed")
    last_reset: HABApp.openhab.items.NumberItem | None = pydantic.Field(None, description="Item which holds the value of the last reset. If set to None, it will be auto-created")


class CounterTaskParameter(habapp_rules.core.pydantic_base.ParameterBase):
    """Parameter for counter task."""

    max_value: int = pydantic.Field(..., description="value, after which the task will be set to active")


class CounterTaskConfig(habapp_rules.core.pydantic_base.ConfigBase):
    """Config for counter task."""

    items: CounterTaskItems = pydantic.Field(..., description="items for counter task")
    parameter: CounterTaskParameter = pydantic.Field(..., description="parameter for counter task")
