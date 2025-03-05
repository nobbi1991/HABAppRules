import collections
import unittest

import HABApp.openhab.items

import habapp_rules.core.exceptions
from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.energy.config.virtual_energy_meter import EnergyMeterBaseItems, EnergyMeterDimmerParameter, PowerMapping


class TestEnergyMeterBaseItems(unittest.TestCase):
    """Tests for EnergyMeterBaseItems."""

    def test_exceptions_with_missing_item(self) -> None:
        """Test exceptions with missing item."""
        TestCase = collections.namedtuple("TestCase", "power_item, energy_item, raises_exc")

        power_item = HABApp.openhab.items.NumberItem("Power")
        energy_item = HABApp.openhab.items.NumberItem("Energy")

        test_cases = [
            TestCase(power_item=None, energy_item=None, raises_exc=True),
            TestCase(power_item=None, energy_item=energy_item, raises_exc=False),
            TestCase(power_item=power_item, energy_item=None, raises_exc=False),
            TestCase(power_item=power_item, energy_item=energy_item, raises_exc=False),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                if test_case.raises_exc:
                    with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
                        EnergyMeterBaseItems(power_output=test_case.power_item, energy_output=test_case.energy_item)
                else:
                    EnergyMeterBaseItems(power_output=test_case.power_item, energy_output=test_case.energy_item)


class TestEnergyMeterDimmerParameter(unittest.TestCase):
    """Tests for EnergyMeterDimmerParameter."""

    def test_get_power(self) -> None:
        """Test get_power."""
        TestCase = collections.namedtuple("TestCase", "mapping, value, expected_result")

        mapping_1 = [PowerMapping(0, 0), PowerMapping(50, 500), PowerMapping(100, 1000)]
        mapping_2 = [PowerMapping(0, 5), PowerMapping(10, 20), PowerMapping(20, 40), PowerMapping(100, 1000)]

        test_cases = [
            # mapping 1
            TestCase(mapping=mapping_1, value=0, expected_result=0),
            TestCase(mapping=mapping_1, value=50, expected_result=500),
            TestCase(mapping=mapping_1, value=100, expected_result=1000),
            TestCase(mapping=mapping_1, value=75, expected_result=750),
            TestCase(mapping=mapping_1, value=-100, expected_result=0),
            TestCase(mapping=mapping_1, value=150, expected_result=1000),
            # mapping 2
            TestCase(mapping=mapping_2, value=0, expected_result=5),
            TestCase(mapping=mapping_2, value=5, expected_result=12.5),
            TestCase(mapping=mapping_2, value=20, expected_result=40),
            TestCase(mapping=mapping_2, value=50, expected_result=400),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                params = EnergyMeterDimmerParameter(power_mapping=test_case.mapping)
                self.assertEqual(test_case.expected_result, params.get_power(test_case.value))

    def test_init_exceptions(self) -> None:
        """Test exceptions at initialization."""
        # mapping list too short
        with self.assertRaises(HabAppRulesConfigurationError):
            EnergyMeterDimmerParameter(power_mapping=[PowerMapping(0, 0)])

        # value below min
        with self.assertRaises(HabAppRulesConfigurationError):
            EnergyMeterDimmerParameter(power_mapping=[PowerMapping(-20, 0), PowerMapping(0, 100)])

        # value above max
        with self.assertRaises(HabAppRulesConfigurationError):
            EnergyMeterDimmerParameter(power_mapping=[PowerMapping(0, 0), PowerMapping(101, 100)])
