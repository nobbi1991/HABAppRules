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
            task_active="I99_99_ToDo_1",
            last_done="I99_99_ToDo_1_last"
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
            self._config.items.last_done.oh_send_command(datetime.datetime.now())

    def _check_and_set_task_undone(self) -> None:
        """Check if task should be set to True."""
        last_done_time = self._config.items.last_done.value if self._config.items.last_done.value is not None else datetime.datetime.min.replace()

        if last_done_time + self._config.parameter.recurrence_time < datetime.datetime.now():
            send_if_different(self._config.items.task_active, "ON")
