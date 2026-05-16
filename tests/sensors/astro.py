"""Test astro rules."""

import collections
import unittest.mock

from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.sensors.astro import SetDay, SetNight
from habapp_rules.sensors.config.astro import SetDayConfig, SetDayItems, SetDayParameter, SetNightConfig, SetNightItems, SetNightParameter
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_change_event,
)
from tests.helper.test_case_base import TestCaseBase


class TestSetDay(TestCaseBase):
    """Tests for TestSetDay."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Elevation", None)
        add_mock_item(SwitchItem, "Unittest_Day", None)

    def test_init(self) -> None:
        """Test init without elevation."""
        # default threshold
        config = SetDayConfig(
            items=SetDayItems(
                day="Unittest_Day",
                elevation="Unittest_Elevation",
            )
        )

        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = SetDay(config)

        run_soon_mock.assert_called_once_with(rule._set_night, None)
        self.assertEqual(0, rule._elevation_threshold)

        # custom threshold
        config.parameter = SetDayParameter(elevation_threshold=-2)
        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = SetDay(config)

        run_soon_mock.assert_called_once_with(rule._set_night, None)
        self.assertEqual(-2, rule._elevation_threshold)

    def test_init_with_elevation(self) -> None:
        """Test init without elevation."""
        TestCase = collections.namedtuple("TestCase", "elevation_value, night_state")

        test_cases = [
            TestCase(None, None),
            TestCase(-1, "OFF"),
            TestCase(0, "OFF"),
            TestCase(0.9, "OFF"),
            TestCase(1, "OFF"),
            TestCase(1.1, "ON"),
            TestCase(2, "ON"),
            TestCase(10, "ON"),
        ]

        config = SetDayConfig(
            items=SetDayItems(
                day="Unittest_Day",
                elevation="Unittest_Elevation",
            ),
            parameter=SetDayParameter(elevation_threshold=1),
        )

        SetDay(config)

        for test_case in test_cases:
            item_state_change_event("Unittest_Elevation", test_case.elevation_value)
            assert_item_value("Unittest_Day", test_case.night_state)


class TestSetNight(TestCaseBase):
    """Tests for TestSetNight."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Elevation", None)
        add_mock_item(SwitchItem, "Unittest_Night", None)

    def test_init(self) -> None:
        """Test init without elevation."""
        # default threshold
        config = SetNightConfig(
            items=SetNightItems(
                night="Unittest_Night",
                elevation="Unittest_Elevation",
            )
        )

        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = SetNight(config)

        run_soon_mock.assert_called_once_with(rule._set_night, None)
        self.assertEqual(-8, rule._elevation_threshold)

        # custom threshold
        config.parameter = SetNightParameter(elevation_threshold=-10)
        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = SetNight(config)

        run_soon_mock.assert_called_once_with(rule._set_night, None)
        self.assertEqual(-10, rule._elevation_threshold)

    def test_init_with_elevation(self) -> None:
        """Test init without elevation."""
        TestCase = collections.namedtuple("TestCase", "elevation_value, night_state")

        test_cases = [
            TestCase(None, None),
            TestCase(-9, "ON"),
            TestCase(-8.1, "ON"),
            TestCase(-8, "OFF"),
            TestCase(-7.9, "OFF"),
            TestCase(-5, "OFF"),
            TestCase(0, "OFF"),
            TestCase(10, "OFF"),
        ]

        config = SetNightConfig(
            items=SetNightItems(
                night="Unittest_Night",
                elevation="Unittest_Elevation",
            ),
            parameter=SetNightParameter(elevation_threshold=-8),
        )

        SetNight(config)

        for test_case in test_cases:
            item_state_change_event("Unittest_Elevation", test_case.elevation_value)
            assert_item_value("Unittest_Night", test_case.night_state)
