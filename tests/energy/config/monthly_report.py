"""Test config models for monthly energy report rules."""

import unittest.mock

from HABApp.openhab.items import NumberItem, SwitchItem

from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.energy.config.monthly_report import EnergyShare
from tests.helper.oh_item import add_mock_item, set_item_state
from tests.helper.test_case_base import TestCaseBase


class TestEnergyShare(TestCaseBase):
    """Test EnergyShare dataclass."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Number_1", None)
        add_mock_item(NumberItem, "Number_2", None)
        add_mock_item(SwitchItem, "Switch_1", None)

    def test_init(self) -> None:
        """Test init."""
        # valid init
        energy_share = EnergyShare("Number_1", "First Number")
        self.assertEqual("Number_1", energy_share.energy_item.name)
        self.assertEqual("First Number", energy_share.chart_name)
        self.assertEqual(0, energy_share.monthly_power)

        expected_item = NumberItem.get_item("Number_1")
        self.assertEqual(expected_item, energy_share.energy_item)

        # valid init with item
        energy_share = EnergyShare(expected_item, "First Number")
        self.assertEqual("Number_1", energy_share.energy_item.name)
        self.assertEqual("First Number", energy_share.chart_name)
        self.assertEqual(0, energy_share.monthly_power)

        # valid init with list of item names
        energy_share = EnergyShare(["Number_1", "Number_2"], "First Number")
        self.assertEqual(["Number_1", "Number_2"], [item.name for item in energy_share.energy_item])
        self.assertEqual("First Number", energy_share.chart_name)
        self.assertEqual(0, energy_share.monthly_power)

        # valid init with list of items
        energy_share = EnergyShare([expected_item, NumberItem.get_item("Number_2")], "First Number")
        self.assertEqual(["Number_1", "Number_2"], [item.name for item in energy_share.energy_item])
        self.assertEqual("First Number", energy_share.chart_name)
        self.assertEqual(0, energy_share.monthly_power)

        # invalid init (Item not found)
        with self.assertRaises(HabAppRulesConfigurationError):
            EnergyShare("Number_3", "Second Number")

        # invalid init (Item is not a number)
        with self.assertRaises(HabAppRulesConfigurationError):
            EnergyShare("Switch_1", "Second Number")

    def test_get_energy_since(self) -> None:
        """Test get_energy_since."""
        # single item
        single = EnergyShare("Number_1", "First Number")
        set_item_state("Number_1", 42)
        with unittest.mock.patch("habapp_rules.energy.config.monthly_report.get_historic_value", side_effect=[12]) as get_historic_value_mock:
            time_mock = unittest.mock.MagicMock()
            self.assertEqual(30, single.get_energy_since(time_mock))
        get_historic_value_mock.assert_called_once_with(single.energy_item, time_mock, 0)

        # multiple items
        multiple = EnergyShare(["Number_1", "Number_2"], "First Number")
        set_item_state("Number_1", 100)
        set_item_state("Number_2", 300)
        with unittest.mock.patch("habapp_rules.energy.config.monthly_report.get_historic_value", side_effect=[50, 100]) as get_historic_value_mock:
            time_mock = unittest.mock.MagicMock()
            self.assertEqual(250, multiple.get_energy_since(time_mock))
        self.assertEqual(2, get_historic_value_mock.call_count)
        get_historic_value_mock.assert_has_calls([unittest.mock.call(multiple.energy_item[0], time_mock, 0), unittest.mock.call(multiple.energy_item[1], time_mock, 0)])

        # negative_value
        single = EnergyShare("Number_1", "First Number")
        set_item_state("Number_1", 42)
        with unittest.mock.patch("habapp_rules.energy.config.monthly_report.get_historic_value", side_effect=[100]) as get_historic_value_mock:
            time_mock = unittest.mock.MagicMock()
            self.assertEqual(0, single.get_energy_since(time_mock))
        get_historic_value_mock.assert_called_once_with(single.energy_item, time_mock, 0)

    def test_get_items_as_list(self) -> None:
        """Test get_items_as_list."""
        # single item
        single = EnergyShare("Number_1", "First Number")
        self.assertEqual(1, len(single.get_items_as_list))
        self.assertEqual("Number_1", single.get_items_as_list[0].name)

        # multiple items
        multiple = EnergyShare(["Number_1", "Number_2"], "First Number")
        self.assertEqual(2, len(multiple.get_items_as_list))
        self.assertEqual("Number_1", multiple.get_items_as_list[0].name)
        self.assertEqual("Number_2", multiple.get_items_as_list[1].name)
