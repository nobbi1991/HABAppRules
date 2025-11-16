import datetime

import HABApp

import habapp_rules.system.config.task
from habapp_rules.core.helper import send_if_different


class RecurringTask(HABApp.Rule):
    """Rule to check and set recurring tasks.

    # Items:
    Switch    Task        "Task"
    DateTime  Task_last   "Task last done".

    # Config:
    config = habapp_rules.system.config.task.RecurringTaskConfig(
        items=habapp_rules.system.config.task.RecurringTaskItems(
            task_active="Task"
        ),
        parameter=habapp_rules.system.config.task.RecurringTaskParameter(
            recurrence_time=datetime.timedelta(hours=12))
    ))

    # Rule init:
    habapp_rules.system.task.RecurringTask(config)
    """

    def __init__(self, config: habapp_rules.system.config.task.RecurringTaskConfig) -> None:
        """Init rule.

        Args:
            config: config for this rule
        """
        HABApp.Rule.__init__(self)
        self._config = config

        if self._config.items.last_done is None:
            last_done_name = f"H_{self._config.items.task_active.name}_last_done"
            habapp_rules.core.helper.create_additional_item(last_done_name, "DateTime")
        else:
            last_done_name = self._config.items.last_done.name
        self._item_last_done = HABApp.openhab.items.DatetimeItem.get_item(last_done_name)

        if self._config.parameter.fixed_check_time is not None:
            self.run.at(self.run.trigger.time(self._config.parameter.fixed_check_time), self._check_and_set_task_undone)
        else:
            self.run.at(self.run.trigger.interval(1, self._get_check_cycle()), self._check_and_set_task_undone)

        self._config.items.task_active.listen_event(self._cb_task_active, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _get_check_cycle(self) -> datetime.timedelta:
        """Get cycle time to check if task is done.

        Returns:
            cycle time
        """
        return self._config.parameter.recurrence_time / 20

    def _cb_task_active(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if the "task_active" item was changed.

        Args:
            event: event, which triggered this callback
        """
        if event.value == "OFF":
            self._item_last_done.oh_send_command(datetime.datetime.now())

    def _check_and_set_task_undone(self) -> None:
        """Check if task should be set to True."""
        last_done_time = self._config.items.last_done.value if self._config.items.last_done.value is not None else datetime.datetime.min.replace()

        if last_done_time + self._config.parameter.recurrence_time < datetime.datetime.now():
            send_if_different(self._config.items.task_active, "ON")


class CounterTask(HABApp.Rule):
    """Rule to check number item and set a switch item to ON if the number is greater than a threshold.

    # Items:
    Switch    Task        "Task"
    Number    Observed   "Observed item"

    # Config:
    config = habapp_rules.system.config.task.CounterTaskConfig(
        items=habapp_rules.system.config.task.CounterTaskItems(
            task_active="Task",
            observed="Observed"
        ),
        parameter=habapp_rules.system.config.task.CounterTaskParameter(
            max_value=42
    ))

    # Rule init:
    habapp_rules.system.task.CounterTask(config)
    """

    def __init__(self, config: habapp_rules.system.config.task.CounterTaskConfig) -> None:
        """Init rule.

        Args:
            config: config for this rule
        """
        HABApp.Rule.__init__(self)
        self._config = config

        if self._config.items.last_reset is None:
            last_reset_name = f"H_{self._config.items.observed.name}_last_reset"
            habapp_rules.core.helper.create_additional_item(last_reset_name, "Number")
        else:
            last_reset_name = self._config.items.last_reset.name
        self._item_last_reset = HABApp.openhab.items.NumberItem.get_item(last_reset_name)

        self._config.items.task_active.listen_event(self._cb_task_active, HABApp.openhab.events.ItemStateChangedEventFilter())
        self._config.items.observed.listen_event(self._cb_observed, HABApp.openhab.events.ItemStateChangedEventFilter())

    def _cb_task_active(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if the "task_active" item was changed.

        Args:
            event: event, which triggered this callback
        """
        if event.value == "OFF" and event.old_value is not None:
            self._item_last_reset.oh_send_command(self._config.items.observed.value)

    def _cb_observed(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if the "observed" item was changed.

        Args:
            event: event, which triggered this callback
        """
        last_value = self._item_last_reset.value or 0

        target_value = "ON" if event.value - last_value > self._config.parameter.max_value else "OFF"
        send_if_different(self._config.items.task_active, target_value)
