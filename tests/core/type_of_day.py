"""Test type of day functions."""

import collections
import datetime
import unittest
import unittest.mock

import habapp_rules.core.type_of_day
from habapp_rules import TIMEZONE


class TestTypeOfDay(unittest.TestCase):
    """Test all type of day functions."""

    def test_is_weekend(self):
        """Test is_weekend."""
        TestCase = collections.namedtuple("TestCase", "day, offset, result")

        test_cases = [
            # Monday
            TestCase(datetime.datetime(2023, 12, 18, tzinfo=TIMEZONE), -1, True),
            TestCase(datetime.datetime(2023, 12, 18, tzinfo=TIMEZONE), 0, False),
            TestCase(datetime.datetime(2023, 12, 18, tzinfo=TIMEZONE), 1, False),
            TestCase(datetime.datetime(2023, 12, 18, tzinfo=TIMEZONE), 2, False),
            # Friday
            TestCase(datetime.datetime(2023, 12, 22, tzinfo=TIMEZONE), -1, False),
            TestCase(datetime.datetime(2023, 12, 22, tzinfo=TIMEZONE), 0, False),
            TestCase(datetime.datetime(2023, 12, 22, tzinfo=TIMEZONE), 1, True),
            TestCase(datetime.datetime(2023, 12, 22, tzinfo=TIMEZONE), 2, True),
            # Saturday
            TestCase(datetime.datetime(2023, 12, 23, tzinfo=TIMEZONE), -1, False),
            TestCase(datetime.datetime(2023, 12, 23, tzinfo=TIMEZONE), 0, True),
            TestCase(datetime.datetime(2023, 12, 23, tzinfo=TIMEZONE), 1, True),
            TestCase(datetime.datetime(2023, 12, 23, tzinfo=TIMEZONE), 2, False),
            # Sunday
            TestCase(datetime.datetime(2023, 12, 24, tzinfo=TIMEZONE), -1, True),
            TestCase(datetime.datetime(2023, 12, 24, tzinfo=TIMEZONE), 0, True),
            TestCase(datetime.datetime(2023, 12, 24, tzinfo=TIMEZONE), 1, False),
            TestCase(datetime.datetime(2023, 12, 24, tzinfo=TIMEZONE), 2, False),
        ]

        with unittest.mock.patch("datetime.datetime") as datetime_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    datetime_mock.now.return_value = test_case.day
                    self.assertEqual(test_case.result, habapp_rules.core.type_of_day.is_weekend(test_case.offset))

    def test_is_holiday(self):
        """Test is_holiday."""
        TestCase = collections.namedtuple("TestCase", "day, offset, result")

        test_cases = [
            # Holy evening
            TestCase(datetime.datetime(2023, 12, 23, tzinfo=TIMEZONE), -1, False),
            TestCase(datetime.datetime(2023, 12, 23, tzinfo=TIMEZONE), 0, False),
            TestCase(datetime.datetime(2023, 12, 23, tzinfo=TIMEZONE), 1, False),
            TestCase(datetime.datetime(2023, 12, 23, tzinfo=TIMEZONE), 2, True),
            # Christmas
            TestCase(datetime.datetime(2023, 12, 25, tzinfo=TIMEZONE), -1, False),
            TestCase(datetime.datetime(2023, 12, 25, tzinfo=TIMEZONE), 0, True),
            TestCase(datetime.datetime(2023, 12, 25, tzinfo=TIMEZONE), 1, True),
            TestCase(datetime.datetime(2023, 12, 25, tzinfo=TIMEZONE), 2, False),
        ]

        with unittest.mock.patch("datetime.datetime") as datetime_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    datetime_mock.now.return_value = test_case.day
                    self.assertEqual(test_case.result, habapp_rules.core.type_of_day.is_holiday(test_case.offset))
