"""Test config models for motion rules."""

import collections

from HABApp.openhab.items import NumberItem, StringItem, SwitchItem

from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.sensors.config.motion import MotionConfig, MotionItems, MotionParameter
from tests.helper.oh_item import (
    add_mock_item,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBase


class TestMotionItems(TestCaseBase):
    """Test MotionItems."""

    def setUp(self) -> None:
        """Setup test environment."""
        super().setUp()
        add_mock_item(SwitchItem, "Unittest_Motion_raw")
        add_mock_item(SwitchItem, "Unittest_Motion_filt")
        add_mock_item(StringItem, "Unittest_Motion_state")

        add_mock_item(NumberItem, "Unittest_Brightness")
        add_mock_item(NumberItem, "Unittest_Brightness_threshold")

    def test_check_brightness_threshold(self) -> None:
        """Test brightness and brightness_threshold."""
        # brightness NOT SET | brightness_threshold NOT SET
        MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state")

        # brightness NOT SET | brightness_threshold SET
        with self.assertRaises(HabAppRulesConfigurationError):
            MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness_threshold="Unittest_Brightness_threshold")

        # brightness SET | brightness_threshold NOT SET
        MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness="Unittest_Brightness")

        # brightness SET | brightness_threshold SET
        MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness="Unittest_Brightness", brightness_threshold="Unittest_Brightness_threshold")


class TestMotionConfig(TestCaseBase):
    """Test MotionConfig."""

    def setUp(self) -> None:
        """Setup test environment."""
        super().setUp()
        add_mock_item(SwitchItem, "Unittest_Motion_raw")
        add_mock_item(SwitchItem, "Unittest_Motion_filt")
        add_mock_item(StringItem, "Unittest_Motion_state")

        add_mock_item(NumberItem, "Unittest_Brightness")
        add_mock_item(NumberItem, "Unittest_Brightness_threshold")

    def test_brightness_validation(self) -> None:
        """Test brightness validation."""
        TestCase = collections.namedtuple("TestCase", ["brightness_item", "threshold_item", "threshold_param", "expect_exception"])

        test_cases = [
            TestCase(brightness_item=False, threshold_item=False, threshold_param=False, expect_exception=False),
            TestCase(brightness_item=False, threshold_item=False, threshold_param=True, expect_exception=False),
            TestCase(brightness_item=False, threshold_item=True, threshold_param=False, expect_exception=True),
            TestCase(brightness_item=False, threshold_item=True, threshold_param=True, expect_exception=True),
            TestCase(brightness_item=True, threshold_item=False, threshold_param=False, expect_exception=True),
            TestCase(brightness_item=True, threshold_item=False, threshold_param=True, expect_exception=False),
            TestCase(brightness_item=True, threshold_item=True, threshold_param=False, expect_exception=False),
            TestCase(brightness_item=True, threshold_item=True, threshold_param=True, expect_exception=True),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                brightness_item = "Unittest_Brightness" if test_case.brightness_item else None
                threshold_item = "Unittest_Brightness_threshold" if test_case.threshold_item else None
                threshold_param = 42 if test_case.threshold_param else None

                if test_case.expect_exception:
                    with self.assertRaises(HabAppRulesConfigurationError):
                        MotionConfig(
                            items=MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness=brightness_item, brightness_threshold=threshold_item),
                            parameter=MotionParameter(brightness_threshold=threshold_param),
                        )
                else:
                    MotionConfig(
                        items=MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness=brightness_item, brightness_threshold=threshold_item),
                        parameter=MotionParameter(brightness_threshold=threshold_param),
                    )

    def test_brightness_threshold(self) -> None:
        """Test brightness_threshold."""
        # value of threshold item (has no value)
        config = MotionConfig(
            items=MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness="Unittest_Brightness", brightness_threshold="Unittest_Brightness_threshold"),
            parameter=MotionParameter(),
        )
        self.assertEqual(float("inf"), config.brightness_threshold)

        # value of threshold item (has value)
        set_item_state("Unittest_Brightness_threshold", 42)
        config = MotionConfig(
            items=MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness="Unittest_Brightness", brightness_threshold="Unittest_Brightness_threshold"),
            parameter=MotionParameter(),
        )
        self.assertEqual(42, config.brightness_threshold)

        # value given as parameter
        config = MotionConfig(
            items=MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness="Unittest_Brightness"),
            parameter=MotionParameter(brightness_threshold=999),
        )
        self.assertEqual(999, config.brightness_threshold)

    def test_brightness_threshold_exceptions(self) -> None:
        """Test exceptions of brightness_threshold."""
        config = MotionConfig(
            items=MotionItems(motion_raw="Unittest_Motion_raw", motion_filtered="Unittest_Motion_filt", state="Unittest_Motion_state", brightness="Unittest_Brightness"),
            parameter=MotionParameter(brightness_threshold=999),
        )

        config.parameter.brightness_threshold = None
        with self.assertRaises(HabAppRulesConfigurationError):
            config.brightness_threshold  # noqa: B018
