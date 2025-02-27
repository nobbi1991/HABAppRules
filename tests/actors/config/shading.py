"""Test config models for shading rules."""

import collections
import unittest
from itertools import starmap

import HABApp
import pydantic

import habapp_rules.actors.config.shading
import habapp_rules.core.exceptions
import tests.helper.oh_item
import tests.helper.test_case_base


class TestShadingConfig(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing ShadingConfig."""

    def tests_validate_model(self) -> None:
        """Test validate_model."""
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.RollershutterItem, "Unittest_Shading", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Shading_state", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Summer", None)

        # parameter NOT given | item summer NOT given
        habapp_rules.actors.config.shading.ShadingConfig(
            items=habapp_rules.actors.config.shading.ShadingItems(shading_position="Unittest_Shading", manual="Unittest_Manual", state="H_Unittest_Shading_state"), parameter=habapp_rules.actors.config.shading.ShadingParameter()
        )

        # parameter NOT given | item summer given
        habapp_rules.actors.config.shading.ShadingConfig(
            items=habapp_rules.actors.config.shading.ShadingItems(shading_position="Unittest_Shading", manual="Unittest_Manual", state="H_Unittest_Shading_state", summer="Unittest_Summer"),
            parameter=habapp_rules.actors.config.shading.ShadingParameter(),
        )

        # parameter given | item summer NOT given
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.actors.config.shading.ShadingConfig(
                items=habapp_rules.actors.config.shading.ShadingItems(shading_position="Unittest_Shading", manual="Unittest_Manual", state="H_Unittest_Shading_state"),
                parameter=habapp_rules.actors.config.shading.ShadingParameter(pos_night_close_summer=habapp_rules.actors.config.shading.ShadingPosition(42, 80)),
            )

        # parameter given | item summer given
        habapp_rules.actors.config.shading.ShadingConfig(
            items=habapp_rules.actors.config.shading.ShadingItems(shading_position="Unittest_Shading", manual="Unittest_Manual", state="H_Unittest_Shading_state", summer="Unittest_Summer"),
            parameter=habapp_rules.actors.config.shading.ShadingParameter(pos_night_close_summer=habapp_rules.actors.config.shading.ShadingPosition(42, 80)),
        )


class TestSlatValueParameter(unittest.TestCase):
    """Test slat value parameter."""

    def test__check_and_sort_characteristic(self) -> None:
        """Test __check_and_sort_characteristic."""
        TestCase = collections.namedtuple("TestCase", "input, expected_output, raises")

        test_cases = [
            TestCase([(0, 100), (10, 50)], [(0, 100), (10, 50)], False),
            TestCase([(10, 50), (0, 100)], [(0, 100), (10, 50)], False),
            TestCase([(0, 100), (10, 50), (20, 50)], [(0, 100), (10, 50), (20, 50)], False),
            TestCase([(10, 50), (0, 100), (20, 50)], [(0, 100), (10, 50), (20, 50)], False),
            TestCase([(10, 50), (20, 50), (0, 100)], [(0, 100), (10, 50), (20, 50)], False),
            TestCase([(0, 50), (0, 40)], None, True),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                input_conf = list(starmap(habapp_rules.actors.config.shading.ElevationSlatMapping, test_case.input))
                output = list(starmap(habapp_rules.actors.config.shading.ElevationSlatMapping, test_case.expected_output)) if test_case.expected_output else None
                if test_case.raises:
                    with self.assertRaises(pydantic.ValidationError):
                        habapp_rules.actors.config.shading.SlatValueParameter(elevation_slat_characteristic=input_conf, elevation_slat_characteristic_summer=input_conf)
                else:
                    config = habapp_rules.actors.config.shading.SlatValueParameter(elevation_slat_characteristic=input_conf, elevation_slat_characteristic_summer=input_conf)

                    self.assertEqual(output, config.elevation_slat_characteristic)
                    self.assertEqual(output, config.elevation_slat_characteristic_summer)
