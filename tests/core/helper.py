"""Unit tests for habapp_rules helper."""

import collections
import time
import unittest.mock

import whenever
from HABApp.core.items.base_item import UpdatedTime
from HABApp.openhab.interface_sync import create_item
from HABApp.openhab.items import DimmerItem, NumberItem, SwitchItem

from habapp_rules.core.exceptions import HabAppRulesError
from habapp_rules.core.helper import create_additional_item, filter_updated_items, send_if_different
from tests.helper.oh_item import add_mock_item, assert_item_value
from tests.helper.test_case_base import TestCaseBase


class TestHelperFunctions(TestCaseBase):
    """Tests for all helper functions."""

    def test_create_additional_item(self) -> None:
        """Test create additional item."""
        # check if item is created if NOT existing
        self.item_exists_mock.return_value = False
        TestCase = collections.namedtuple("TestCase", "item_class, item_type_name, name, label_input, label_call, groups")

        test_cases = [
            TestCase(SwitchItem, "Switch", "Item_name", "Some label", "Some label", None),
            TestCase(SwitchItem, "Switch", "Item_name", None, "Item name", None),
            TestCase(SwitchItem, "Switch", "Item_name", "Some label", "Some label", None),
            TestCase(SwitchItem, "Switch", "Item_name", "Some label", "Some label", None),
            TestCase(SwitchItem, "Switch", "Item_name", None, "Item name", None),
            TestCase(SwitchItem, "Switch", "Item_name", None, "Item name", ["test_group"]),
            TestCase(NumberItem, "Number", "Item_name", "Some label", "Some label", None),
        ]

        with unittest.mock.patch("habapp_rules.core.helper.create_item", spec=create_item) as create_mock, unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
            for test_case in test_cases:
                create_mock.reset_mock()
                create_additional_item(test_case.name, test_case.item_class, test_case.label_input, test_case.groups)
                create_mock.assert_called_once_with(item_type=test_case.item_type_name, name=f"H_{test_case.name}", label=test_case.label_call, groups=test_case.groups)

        # check if item is NOT created if existing
        self.item_exists_mock.return_value = True
        with unittest.mock.patch("habapp_rules.core.helper.create_item", spec=create_item) as create_mock, unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
            create_additional_item("Name_of_Item", SwitchItem)
            create_mock.assert_not_called()

    def test_test_create_additional_item_exception(self) -> None:
        """Test exceptions of _create_additional_item."""
        self.item_exists_mock.return_value = False
        with unittest.mock.patch("habapp_rules.core.helper.create_item", spec=create_item, return_value=False), self.assertRaises(HabAppRulesError):
            create_additional_item("Name_of_Item", SwitchItem)

    def test_send_if_different(self) -> None:
        """Test send_if_different."""
        # item given
        add_mock_item(NumberItem, "Unittest_Number", 0)
        number_item = NumberItem.get_item("Unittest_Number")

        send_if_different(number_item, 0)
        assert_item_value("Unittest_Number", 0)

        send_if_different(number_item, 42)
        assert_item_value("Unittest_Number", 42)

        # name given
        send_if_different("Unittest_Number", 42)
        assert_item_value("Unittest_Number", 42)

        send_if_different("Unittest_Number", 84)
        assert_item_value("Unittest_Number", 84)


class TestHelperWithItems(TestCaseBase):
    """Test helper functions with OpenHAB items."""

    def test_filter_updated_items(self) -> None:
        """Test filter_updated_items."""
        add_mock_item(NumberItem, "Unittest_Number", 0)
        add_mock_item(DimmerItem, "Unittest_Dimmer", 0)
        add_mock_item(SwitchItem, "Unittest_Switch", "OFF")

        item_number = NumberItem.get_item("Unittest_Number")
        item_dimmer = DimmerItem.get_item("Unittest_Dimmer")
        item_switch = SwitchItem.get_item("Unittest_Switch")

        # without filter
        result = filter_updated_items([item_number, item_dimmer, item_switch])
        self.assertListEqual([item_number, item_dimmer, item_switch], result)

        # with filter
        result = filter_updated_items([item_number, item_dimmer, item_switch], 60)
        self.assertListEqual([item_number, item_dimmer, item_switch], result)

        item_dimmer._last_update = UpdatedTime("Unittest_Dimmer", whenever.Instant.from_timestamp(time.time() - 61))
        result = filter_updated_items([item_number, item_dimmer, item_switch], 60)
        self.assertListEqual([item_number, item_switch], result)
