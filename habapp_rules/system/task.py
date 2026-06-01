import datetime

from HABApp.openhab.events import ItemStateChangedEvent
from HABApp.openhab.events.event_filters import ItemStateChangedEventFilter

from habapp_rules.core.base import RuleBase
from habapp_rules.core.helper import send_if_different
from habapp_rules.system.config.task import CounterTaskConfig, RecurringTaskConfig


class RecurringTask(RuleBase):
    """Rule to check and set recurring tasks.

    # Items:
    Switch    Task        "Task"
    DateTime  Task_last   "Task last done".

    # Config:
    config = RecurringTaskConfig(
        items=RecurringTaskItems(
            task_active="Task"
        ),
        parameter=RecurringTaskParameter(
            recurrence_time=datetime.timedelta(hours=12))
    )

    # Rule init:
    RecurringTask(config)
    """

    def __init__(self, config: RecurringTaskConfig) -> None:
        """Init rule.

        Args:
            config: config for this rule
        """
        RuleBase.__init__(self, config.items.task_active.name)
        self._config = config

        if self._config.parameter.fixed_check_time is not None:
            self.run.at(self.run.trigger.time(self._config.parameter.fixed_check_time), self._check_and_set_task_undone)
        else:
            self.run.at(self.run.trigger.interval(1, self._get_check_cycle()), self._check_and_set_task_undone)

        self._config.items.task_active.listen_event(self._cb_task_active, ItemStateChangedEventFilter())
        self._log_init_done()

    def _get_check_cycle(self) -> datetime.timedelta:
        """Get cycle time to check if task is done.

        Returns:
            cycle time
        """
        return self._config.parameter.recurrence_time / 20

    def _cb_task_active(self, event: ItemStateChangedEvent) -> None:
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


class CounterTask(RuleBase):
    """Rule to check number item and set a switch item to ON if the number is greater than a threshold.

    # Items:
    Switch    Task        "Task"
    Number    Observed   "Observed item"

    # Config:
    config = CounterTaskConfig(
        items=CounterTaskItems(
            task_active="Task",
            observed="Observed"
        ),
        parameter=CounterTaskParameter(
            max_value=42
    ))

    # Rule init:
    CounterTask(config)
    """

    def __init__(self, config: CounterTaskConfig) -> None:
        """Init rule.

        Args:
            config: config for this rule
        """
        RuleBase.__init__(self, config.items.task_active.name)
        self._config = config

        self._config.items.task_active.listen_event(self._cb_task_active, ItemStateChangedEventFilter())
        self._config.items.observed.listen_event(self._cb_observed, ItemStateChangedEventFilter())
        self._log_init_done()

    def _cb_task_active(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is called if the "task_active" item was changed.

        Args:
            event: event, which triggered this callback
        """
        if event.value == "OFF" and event.old_value is not None:
            self._config.items.last_reset.oh_send_command(self._config.items.observed.value)

    def _cb_observed(self, event: ItemStateChangedEvent) -> None:
        """Callback, which is called if the "observed" item was changed.

        Args:
            event: event, which triggered this callback
        """
        last_value = self._config.items.last_reset.value or 0

        target_value = "ON" if event.value - last_value > self._config.parameter.max_value else "OFF"
        send_if_different(self._config.items.task_active, target_value)
