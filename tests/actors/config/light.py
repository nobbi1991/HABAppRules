"""Test config models for light rules."""

import collections
import unittest.mock

import HABApp
import pydantic

import habapp_rules.actors.config.light
import habapp_rules.core.exceptions
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.actors.config.light import BrightnessTimeout, FunctionConfig, LightParameter


class TestBrightnessTimeout(unittest.TestCase):
    """Tests for BrightnessTimeout."""

    def test_post_init(self) -> None:
        """Test post init checks."""
        TestCase = collections.namedtuple("TestCase", "value, timeout, valid")

        test_cases = [
            # valid config
            TestCase(100, 1, True),
            TestCase(1, 100, True),
            TestCase(True, 20, True),
            TestCase(False, 0, True),
            TestCase(False, 10, True),
            TestCase(False, 100, True),
            TestCase(0, 100, True),
            # not valid
            TestCase(100, 0, False),
            TestCase(True, 0, False),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                if test_case.valid:
                    brightness_timeout = BrightnessTimeout(test_case.value, test_case.timeout)
                    self.assertEqual(test_case.value, brightness_timeout.brightness)
                    if test_case.value is False:
                        if test_case.timeout:
                            self.assertEqual(test_case.timeout, brightness_timeout.timeout)
                        else:
                            self.assertEqual(0.5, brightness_timeout.timeout)
                else:
                    with self.assertRaises(pydantic.ValidationError):
                        BrightnessTimeout(test_case.value, test_case.timeout)


class TestLightParameter(unittest.TestCase):
    """Tests for LightParameter."""

    def test_post_init(self) -> None:
        """Test check in post init."""
        TestCase = collections.namedtuple("TestCase", "on, pre_off, leaving, pre_sleep, pre_sleep_prevent, valid")

        func_int = FunctionConfig(day=BrightnessTimeout(80, 3), night=BrightnessTimeout(40, 2), sleeping=BrightnessTimeout(20, 1))
        func_int_partial1 = FunctionConfig(day=None, night=BrightnessTimeout(40, 2), sleeping=BrightnessTimeout(20, 1))
        func_int_partial2 = FunctionConfig(day=BrightnessTimeout(80, 3), night=None, sleeping=BrightnessTimeout(20, 1))
        func_int_partial3 = FunctionConfig(day=BrightnessTimeout(80, 3), night=BrightnessTimeout(40, 2), sleeping=None)
        func_bool = FunctionConfig(day=BrightnessTimeout(True, 3), night=BrightnessTimeout(True, 2), sleeping=BrightnessTimeout(True, 1))

        test_cases = [
            TestCase(on=func_bool, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=True),
            TestCase(on=func_bool, pre_off=func_bool, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=True),
            TestCase(on=func_bool, pre_off=func_bool, leaving=func_bool, pre_sleep=None, pre_sleep_prevent=None, valid=True),
            TestCase(on=func_bool, pre_off=func_bool, leaving=func_bool, pre_sleep=func_bool, pre_sleep_prevent=None, valid=True),
            TestCase(on=func_int, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=True),
            TestCase(on=func_int, pre_off=func_int, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=True),
            TestCase(on=func_int, pre_off=func_int, leaving=func_int, pre_sleep=None, pre_sleep_prevent=None, valid=True),
            TestCase(on=func_int, pre_off=func_int, leaving=func_int, pre_sleep=func_int, pre_sleep_prevent=None, valid=True),
            TestCase(on=None, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
            TestCase(on=None, pre_off=func_bool, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
            TestCase(on=None, pre_off=func_bool, leaving=func_bool, pre_sleep=None, pre_sleep_prevent=None, valid=False),
            TestCase(on=None, pre_off=func_bool, leaving=func_bool, pre_sleep=func_bool, pre_sleep_prevent=None, valid=False),
            TestCase(on=None, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
            TestCase(on=None, pre_off=func_int, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
            TestCase(on=None, pre_off=func_int, leaving=func_int, pre_sleep=None, pre_sleep_prevent=None, valid=False),
            TestCase(on=None, pre_off=func_int, leaving=func_int, pre_sleep=func_int, pre_sleep_prevent=None, valid=False),
            TestCase(on=func_int_partial1, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
            TestCase(on=func_int_partial2, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
            TestCase(on=func_int_partial3, pre_off=None, leaving=None, pre_sleep=None, pre_sleep_prevent=None, valid=False),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                if test_case.valid:
                    LightParameter(on=test_case.on, pre_off=test_case.pre_off, leaving=test_case.leaving, pre_sleep=test_case.pre_sleep, pre_sleep_prevent=test_case.pre_sleep_prevent)
                else:
                    with self.assertRaises(pydantic.ValidationError):
                        LightParameter(on=test_case.on, pre_off=test_case.pre_off, leaving=test_case.leaving, pre_sleep=test_case.pre_sleep, pre_sleep_prevent=test_case.pre_sleep_prevent)

    def test_sleep_of_pre_sleep(self) -> None:
        """Test if sleep of pre_sleep is set correctly."""
        light_config = LightParameter(
            on=FunctionConfig(day=BrightnessTimeout(True, 3), night=BrightnessTimeout(True, 2), sleeping=BrightnessTimeout(True, 1)), pre_off=None, leaving=None, pre_sleep=FunctionConfig(day=None, night=None, sleeping=BrightnessTimeout(True, 1))
        )

        self.assertIsNone(light_config.pre_sleep.sleeping)


class TestLightConfig(tests.helper.test_case_base.TestCaseBase):
    """Tests for LightConfig."""

    def test_validate_config(self) -> None:
        """Test validate_config."""
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_CustomState", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Sleep_prevent", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Motion", None)

        # ======= min config =======
        habapp_rules.actors.config.light.LightConfig(
            items=habapp_rules.actors.config.light.LightItems(
                light="Unittest_Light",
                manual="Unittest_Manual",
                day="Unittest_Day",
                state="H_CustomState",
            )
        )

        # ======= validate motion =======
        # motion correctly configured
        habapp_rules.actors.config.light.LightConfig(
            items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", motion="Unittest_Motion"),
            parameter=habapp_rules.actors.config.light.LightParameter(motion=FunctionConfig(day=None, night=None, sleeping=None)),
        )

        # motion parameter is missing
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.actors.config.light.LightConfig(items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", motion="Unittest_Motion"))

        # ======= validate door =======
        # door correctly configured
        habapp_rules.actors.config.light.LightConfig(
            items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", doors=["Unittest_Door_1"]),
            parameter=habapp_rules.actors.config.light.LightParameter(door=FunctionConfig(day=None, night=None, sleeping=None)),
        )

        # door parameter is missing
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.actors.config.light.LightConfig(items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", doors=["Unittest_Door_1"]))

        # ======= validate sleep =======
        # sleep correctly configured
        habapp_rules.actors.config.light.LightConfig(
            items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", sleeping_state="Unittest_Sleep_state"),
            parameter=habapp_rules.actors.config.light.LightParameter(pre_sleep=FunctionConfig(day=None, night=None, sleeping=None)),
        )

        # sleep parameter is missing
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.actors.config.light.LightConfig(
                items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", sleeping_state="Unittest_Sleep_state"),
                parameter=habapp_rules.actors.config.light.LightParameter(pre_sleep=None),
            )

        # ======= validate presence =======
        # presence correctly configured
        habapp_rules.actors.config.light.LightConfig(
            items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", presence_state="Unittest_Presence_state"),
            parameter=habapp_rules.actors.config.light.LightParameter(leaving=FunctionConfig(day=None, night=None, sleeping=None)),
        )

        # presence parameter is missing
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.actors.config.light.LightConfig(
                items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", presence_state="Unittest_Presence_state"),
                parameter=habapp_rules.actors.config.light.LightParameter(leaving=None),
            )

        # ======= validate sleep_prevent =======
        # warning if item and parameter are given
        with unittest.mock.patch.object(habapp_rules.actors.config.light.LOGGER, "warning") as mock_warning:
            habapp_rules.actors.config.light.LightConfig(
                items=habapp_rules.actors.config.light.LightItems(light="Unittest_Light", manual="Unittest_Manual", day="Unittest_Day", state="H_CustomState", pre_sleep_prevent="Unittest_Sleep_prevent"),
                parameter=habapp_rules.actors.config.light.LightParameter(pre_sleep_prevent=unittest.mock.Mock()),
            )
        mock_warning.assert_called_once()
