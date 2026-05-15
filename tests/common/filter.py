"""Unit-test for filter functions / rules."""

import collections

from HABApp.openhab.items import NumberItem

from habapp_rules.common.config.filter import ExponentialFilterConfig, ExponentialFilterItems, ExponentialFilterParameter
from habapp_rules.common.filter import ExponentialFilter
from tests.helper.oh_item import add_mock_item, assert_item_value, item_state_change_event, set_item_state
from tests.helper.test_case_base import TestCaseBase


class TestExponentialFilter(TestCaseBase):
    """Tests ExponentialFilter."""

    def setUp(self) -> None:
        """Setup unit-tests."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Raw", None)
        add_mock_item(NumberItem, "Unittest_Filtered", None)
        add_mock_item(NumberItem, "Unittest_Filtered_2", None)

        config = ExponentialFilterConfig(items=ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"), parameter=ExponentialFilterParameter(tau=10))

        config_increase = ExponentialFilterConfig(items=ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered_2"), parameter=ExponentialFilterParameter(tau=100, instant_increase=True))

        self.filter = ExponentialFilter(config)
        self.filter_increase = ExponentialFilter(config_increase)

    def test__init__(self) -> None:
        """Test __init__."""
        self.assertEqual("Unittest_Raw", self.filter._config.items.raw.name)
        self.assertEqual("Unittest_Raw", self.filter_increase._config.items.raw.name)

        self.assertEqual("Unittest_Filtered", self.filter._config.items.filtered.name)
        self.assertEqual("Unittest_Filtered_2", self.filter_increase._config.items.filtered.name)

        self.assertEqual(0.2, self.filter._alpha)
        self.assertEqual(0.2, self.filter_increase._alpha)

        self.assertFalse(self.filter._config.parameter.instant_increase)
        self.assertFalse(self.filter._config.parameter.instant_decrease)

        self.assertTrue(self.filter_increase._config.parameter.instant_increase)
        self.assertFalse(self.filter_increase._config.parameter.instant_decrease)

    def test_cb_cyclic_calculate_and_update_output(self) -> None:
        """Test _cb_cyclic_calculate_and_update_output."""
        TestCase = collections.namedtuple("TestCase", "new_value, previous_value, expected_result")

        test_cases = [
            TestCase(1, 1, 1),
            TestCase(2, 1, 1.2),
            TestCase(2, 0, 0.4),
            TestCase(0, 2, 1.6),
            TestCase(None, None, 999),
            TestCase(None, 42, 999),
            TestCase(42, None, 999),
        ]

        for test_case in test_cases:
            set_item_state("Unittest_Raw", test_case.new_value)
            set_item_state("Unittest_Filtered", 999)  # set some random value
            self.filter._previous_value = test_case.previous_value

            self.filter._cb_cyclic_calculate_and_update_output()

            self.assertEqual(test_case.expected_result, round(self.filter._config.items.filtered.value, 2))

            if test_case.new_value is not None and test_case.previous_value is not None:
                self.assertEqual(test_case.expected_result, round(self.filter._previous_value, 2))
            else:
                self.assertEqual(test_case.previous_value, self.filter._previous_value)

    def test_cb_item_raw(self) -> None:
        """Test _cb_item_raw."""
        TestCase = collections.namedtuple("TestCase", "new_value, previous_value, instant_increase, instant_decrease, expected_value")

        test_cases = [
            TestCase(200, 100, False, False, 100),
            TestCase(200, 100, False, True, 100),
            TestCase(200, 100, True, False, 200),
            TestCase(200, None, False, False, 200),
            TestCase(200, None, False, True, 200),
            TestCase(200, None, True, False, 200),
            TestCase(50, 100, False, False, 100),
            TestCase(50, 100, False, True, 50),
            TestCase(50, 100, True, False, 100),
            TestCase(50, None, False, False, 50),
            TestCase(50, None, False, True, 50),
            TestCase(50, None, True, False, 50),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("Unittest_Filtered_2", 100)  # set some "random" value
                self.filter_increase._previous_value = test_case.previous_value
                self.filter_increase._config.parameter.instant_increase = test_case.instant_increase
                self.filter_increase._config.parameter.instant_decrease = test_case.instant_decrease

                item_state_change_event("Unittest_Raw", test_case.new_value)

                assert_item_value("Unittest_Filtered_2", test_case.expected_value)
