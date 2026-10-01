"""Unit tests for habapp_rules helper."""

import collections
import time
import unittest.mock

import whenever
from HABApp.openhab.items import DimmerItem, NumberItem, SwitchItem

from habapp_rules.core.exceptions import HabAppRulesError
from habapp_rules.core.helper import _create_item, _item_exists, create_additional_item, filter_updated_items, send_if_different
from tests.helper.oh_item import add_mock_item, assert_item_value
from tests.helper.test_case_base import TestCaseBase


class TestHelper(TestCaseBase):
    """Tests for all helper functions."""

    def test_create_additional_item(self) -> None:
        """Test create additional item."""
        # check if item is created if NOT existing
        self.item_exists_mock.return_value = False
        TestCase = collections.namedtuple("TestCase", "item_class, item_type_name, name, label_input, label_call, groups")

        test_cases = [
            TestCase(SwitchItem, "Switch", "Item_name", "Some label", "Some label", None),
            TestCase(SwitchItem, "Switch", "Item_name", None, "Item name", None),
            TestCase(SwitchItem, "Switch", "Item_name", None, "Item name", ["test_group"]),
            TestCase(NumberItem, "Number", "Item_name", "Some label", "Some label", None),
        ]

        with unittest.mock.patch("habapp_rules.core.helper._create_item", spec=_create_item) as create_mock, unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
            for test_case in test_cases:
                create_mock.reset_mock()
                create_additional_item(test_case.name, test_case.item_class, test_case.label_input, test_case.groups)
                create_mock.assert_called_once_with(item_type=test_case.item_type_name, name=f"H_{test_case.name}", label=test_case.label_call, groups=test_case.groups)

        # check if item is NOT created if existing
        self.item_exists_mock.return_value = True
        with unittest.mock.patch("habapp_rules.core.helper._create_item", spec=_create_item) as create_mock, unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
            create_additional_item("Name_of_Item", SwitchItem)
            create_mock.assert_not_called()

    def test_create_additional_item_exception(self) -> None:
        """Test exceptions of create_additional_item."""
        self.item_exists_mock.return_value = False
        with unittest.mock.patch("habapp_rules.core.helper._create_item", spec=_create_item, return_value=False), self.assertRaises(HabAppRulesError):
            create_additional_item("Name_of_Item", SwitchItem)

    def test_item_exists(self) -> None:
        """Test _item_exists."""
        with unittest.mock.patch("habapp_rules.core.helper.HABAPP_PROVIDER") as provider_mock:
            interface_mock = provider_mock.get_existing.return_value
            for exists in (True, False):
                interface_mock.item_exists.return_value = exists
                self.assertEqual(exists, _item_exists("Item_name"))
                interface_mock.item_exists.assert_called_with("Item_name")

    def test_create_item(self) -> None:
        """Test _create_item."""
        with unittest.mock.patch("habapp_rules.core.helper.HABAPP_PROVIDER") as provider_mock:
            interface_mock = provider_mock.get_existing.return_value
            for created in (True, False):
                interface_mock.create_item.return_value = created
                self.assertEqual(created, _create_item("Switch", "H_Item_name", "Label", ["group"]))
                interface_mock.create_item.assert_called_with(item_type="Switch", name="H_Item_name", label="Label", groups=["group"])

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

        item_dimmer._last_update.set(whenever.Instant.from_timestamp(time.time() - 61), events=False)
        result = filter_updated_items([item_number, item_dimmer, item_switch], 60)
        self.assertListEqual([item_number, item_switch], result)
