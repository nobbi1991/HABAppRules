"""Test config models for shading rules."""

import collections
import unittest
from itertools import starmap

from HABApp.openhab.items import RollershutterItem, StringItem, SwitchItem

from habapp_rules.actors.config.shading import ElevationSlatMapping, ShadingConfig, ShadingItems, ShadingParameter, ShadingPosition, SlatValueParameter
from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from tests.helper.oh_item import add_mock_item
from tests.helper.test_case_base import TestCaseBase


class TestShadingConfig(TestCaseBase):
    """Tests cases for testing ShadingConfig."""

    def tests_validate_model(self) -> None:
        """Test validate_model."""
        add_mock_item(RollershutterItem, "Unittest_Shading", None)
        add_mock_item(SwitchItem, "Unittest_Manual", None)
        add_mock_item(StringItem, "H_Unittest_Shading_state", None)
        add_mock_item(SwitchItem, "Unittest_Summer", None)

        # parameter NOT given | item summer NOT given
        ShadingConfig(items=ShadingItems(shading_position="Unittest_Shading", manual="Unittest_Manual", state="H_Unittest_Shading_state"), parameter=ShadingParameter())

        # parameter NOT given | item summer given
        ShadingConfig(
            items=ShadingItems(shading_position="Unittest_Shading", manual="Unittest_Manual", state="H_Unittest_Shading_state", summer="Unittest_Summer"),
            parameter=ShadingParameter(),
        )

        # parameter given | item summer NOT given
        with self.assertRaises(HabAppRulesConfigurationError):
            ShadingConfig(
                items=ShadingItems(shading_position="Unittest_Shading", manual="Unittest_Manual", state="H_Unittest_Shading_state"),
                parameter=ShadingParameter(pos_night_close_summer=ShadingPosition(42, 80)),
            )

        # parameter given | item summer given
        ShadingConfig(
            items=ShadingItems(shading_position="Unittest_Shading", manual="Unittest_Manual", state="H_Unittest_Shading_state", summer="Unittest_Summer"),
            parameter=ShadingParameter(pos_night_close_summer=ShadingPosition(42, 80)),
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
                input_conf = list(starmap(ElevationSlatMapping, test_case.input))
                output = list(starmap(ElevationSlatMapping, test_case.expected_output)) if test_case.expected_output else None
                if test_case.raises:
                    with self.assertRaises(HabAppRulesConfigurationError):
                        SlatValueParameter(elevation_slat_characteristic=input_conf, elevation_slat_characteristic_summer=input_conf)
                else:
                    config = SlatValueParameter(elevation_slat_characteristic=input_conf, elevation_slat_characteristic_summer=input_conf)

                    self.assertEqual(output, config.elevation_slat_characteristic)
                    self.assertEqual(output, config.elevation_slat_characteristic_summer)
