import datetime
import unittest

from habapp_rules.system.config.task import RecurringTaskParameter


class TestRecurringTaskParameter(unittest.TestCase):
    """Test RecurringTaskParameter."""

    def test_validation(self) -> None:
        """Test validation of RecurringTaskParameter."""
        # valid (time greater than 12 hours)
        RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=13))

        # valid (time equal 12 hours)
        RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=12))

        # invalid (time less than 12 hours)
        with self.assertRaises(ValueError):
            RecurringTaskParameter(recurrence_time=datetime.timedelta(hours=11))
