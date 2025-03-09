import collections
import unittest

import HABApp.openhab.items

import habapp_rules.core.exceptions
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.energy.config.virtual_energy_meter import EnergyMeterBaseItems, EnergyMeterNumberConfig, EnergyMeterNumberItems, EnergyMeterNumberParameter, PowerMapping


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


class TestEnergyMeterNumberParameter(unittest.TestCase):
    """Tests for EnergyMeterNumberParameter."""

    def test_get_power(self) -> None:
        """Test get_power."""
        TestCase = collections.namedtuple("TestCase", "mapping, value, expected_result")

        mapping_1 = [PowerMapping(0, 0), PowerMapping(50, 500), PowerMapping(100, 1000)]
        mapping_2 = [PowerMapping(0, 5), PowerMapping(10, 20), PowerMapping(20, 40), PowerMapping(100, 1000)]
        mapping_3 = [PowerMapping(-10, 10), PowerMapping(10, -10)]

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
            # mapping 3
            TestCase(mapping=mapping_3, value=-10, expected_result=10),
            TestCase(mapping=mapping_3, value=0, expected_result=0),
            TestCase(mapping=mapping_3, value=10, expected_result=-10),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                params = EnergyMeterNumberParameter(power_mapping=test_case.mapping)
                self.assertEqual(test_case.expected_result, params.get_power(test_case.value))

    def test_init_exceptions(self) -> None:
        """Test exceptions at initialization."""
        # mapping list too short
        with self.assertRaises(HabAppRulesConfigurationError):
            EnergyMeterNumberParameter(power_mapping=[PowerMapping(0, 0)])


class TestEnergyMeterNumberConfig(tests.helper.test_case_base.TestCaseBase):
    """Test EnergyMeterNumberConfig."""

    def setUp(self) -> None:
        """Set up tests."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Power", None)

    def test_init_exceptions(self) -> None:
        """Test exceptions at initialization."""
        # value below min (with DimmerItem)
        with self.assertRaises(HabAppRulesConfigurationError):
            EnergyMeterNumberConfig(items=EnergyMeterNumberItems(monitored_item="Unittest_Dimmer", power_output="Unittest_Power"), parameter=EnergyMeterNumberParameter(power_mapping=[PowerMapping(-20, 0), PowerMapping(0, 100)]))

        # value above max (with DimmerItem)
        with self.assertRaises(HabAppRulesConfigurationError):
            EnergyMeterNumberConfig(items=EnergyMeterNumberItems(monitored_item="Unittest_Dimmer", power_output="Unittest_Power"), parameter=EnergyMeterNumberParameter(power_mapping=[PowerMapping(0, 0), PowerMapping(101, 100)]))
