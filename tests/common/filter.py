"""Unit-test for filter functions / rules."""

import collections

import HABApp

import habapp_rules.common.config.filter
import habapp_rules.common.filter
import tests.helper.oh_item
import tests.helper.test_case_base


class TestExponentialFilter(tests.helper.test_case_base.TestCaseBase):
    """Tests ExponentialFilter."""

    def setUp(self) -> None:
        """Setup unit-tests."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Raw", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Filtered", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Filtered_2", None)

        config = habapp_rules.common.config.filter.ExponentialFilterConfig(
            items=habapp_rules.common.config.filter.ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"), parameter=habapp_rules.common.config.filter.ExponentialFilterParameter(tau=10)
        )

        config_increase = habapp_rules.common.config.filter.ExponentialFilterConfig(
            items=habapp_rules.common.config.filter.ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered_2"), parameter=habapp_rules.common.config.filter.ExponentialFilterParameter(tau=100, instant_increase=True)
        )

        self.filter = habapp_rules.common.filter.ExponentialFilter(config)
        self.filter_increase = habapp_rules.common.filter.ExponentialFilter(config_increase)

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
            tests.helper.oh_item.set_state("Unittest_Raw", test_case.new_value)
            tests.helper.oh_item.set_state("Unittest_Filtered", 999)  # set some random value
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
                tests.helper.oh_item.set_state("Unittest_Filtered_2", 100)  # set some "random" value
                self.filter_increase._previous_value = test_case.previous_value
                self.filter_increase._config.parameter.instant_increase = test_case.instant_increase
                self.filter_increase._config.parameter.instant_decrease = test_case.instant_decrease

                tests.helper.oh_item.item_state_change_event("Unittest_Raw", test_case.new_value)

                tests.helper.oh_item.assert_value("Unittest_Filtered_2", test_case.expected_value)
