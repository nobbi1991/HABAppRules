"""Test astro rules."""

import collections
import unittest.mock

import HABApp.rule.rule

import habapp_rules.sensors.astro
import habapp_rules.sensors.config.astro
import tests.helper.oh_item
import tests.helper.test_case_base


class TestSetDay(tests.helper.test_case_base.TestCaseBase):
    """Tests for TestSetDay."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Elevation", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", None)

    def test_init(self) -> None:
        """Test init without elevation."""
        # default threshold
        config = habapp_rules.sensors.config.astro.SetDayConfig(
            items=habapp_rules.sensors.config.astro.SetDayItems(
                day="Unittest_Day",
                elevation="Unittest_Elevation",
            )
        )

        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = habapp_rules.sensors.astro.SetDay(config)

        run_soon_mock.assert_called_once_with(rule._set_night)
        self.assertEqual(0, rule._elevation_threshold)

        # custom threshold
        config.parameter = habapp_rules.sensors.config.astro.SetDayParameter(elevation_threshold=-2)
        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = habapp_rules.sensors.astro.SetDay(config)

        run_soon_mock.assert_called_once_with(rule._set_night)
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

        config = habapp_rules.sensors.config.astro.SetDayConfig(
            items=habapp_rules.sensors.config.astro.SetDayItems(
                day="Unittest_Day",
                elevation="Unittest_Elevation",
            ),
            parameter=habapp_rules.sensors.config.astro.SetDayParameter(elevation_threshold=1),
        )

        habapp_rules.sensors.astro.SetDay(config)

        for test_case in test_cases:
            tests.helper.oh_item.item_state_change_event("Unittest_Elevation", test_case.elevation_value)
            tests.helper.oh_item.assert_value("Unittest_Day", test_case.night_state)


class TestSetNight(tests.helper.test_case_base.TestCaseBase):
    """Tests for TestSetNight."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Elevation", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Night", None)

    def test_init(self) -> None:
        """Test init without elevation."""
        # default threshold
        config = habapp_rules.sensors.config.astro.SetNightConfig(
            items=habapp_rules.sensors.config.astro.SetNightItems(
                night="Unittest_Night",
                elevation="Unittest_Elevation",
            )
        )

        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = habapp_rules.sensors.astro.SetNight(config)

        run_soon_mock.assert_called_once_with(rule._set_night)
        self.assertEqual(-8, rule._elevation_threshold)

        # custom threshold
        config.parameter = habapp_rules.sensors.config.astro.SetNightParameter(elevation_threshold=-10)
        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = habapp_rules.sensors.astro.SetNight(config)

        run_soon_mock.assert_called_once_with(rule._set_night)
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

        config = habapp_rules.sensors.config.astro.SetNightConfig(
            items=habapp_rules.sensors.config.astro.SetNightItems(
                night="Unittest_Night",
                elevation="Unittest_Elevation",
            ),
            parameter=habapp_rules.sensors.config.astro.SetNightParameter(elevation_threshold=-8),
        )

        habapp_rules.sensors.astro.SetNight(config)

        for test_case in test_cases:
            tests.helper.oh_item.item_state_change_event("Unittest_Elevation", test_case.elevation_value)
            tests.helper.oh_item.assert_value("Unittest_Night", test_case.night_state)
