"""Unit tests for habapp_rules helper."""

import collections
import time
import unittest.mock

import HABApp
import whenever

import habapp_rules.core.exceptions
import habapp_rules.core.helper
import tests.helper.oh_item
import tests.helper.test_case_base


class TestHelperFunctions(tests.helper.test_case_base.TestCaseBase):
    """Tests for all helper functions."""

    def test_create_additional_item(self) -> None:
        """Test create additional item."""
        # check if item is created if NOT existing
        self.item_exists_mock.return_value = False
        TestCase = collections.namedtuple("TestCase", "item_type, name, label_input, label_call, groups")

        test_cases = [
            TestCase("Switch", "Item_name", "Some label", "Some label", None),
            TestCase("Switch", "Item_name", None, "Item name", None),
            TestCase("String", "Item_name", "Some label", "Some label", None),
            TestCase("String", "Item_name", "Some label", "Some label", None),
            TestCase("String", "Item_name", None, "Item name", None),
            TestCase("String", "Item_name", None, "Item name", ["test_group"]),
        ]

        with unittest.mock.patch("HABApp.openhab.interface_sync.create_item", spec=HABApp.openhab.interface_sync.create_item) as create_mock, unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
            for test_case in test_cases:
                create_mock.reset_mock()
                habapp_rules.core.helper.create_additional_item(test_case.name, test_case.item_type, test_case.label_input, test_case.groups)
                create_mock.assert_called_once_with(item_type=test_case.item_type, name=f"H_{test_case.name}", label=test_case.label_call, groups=test_case.groups)

        # check if item is NOT created if existing
        self.item_exists_mock.return_value = True
        with unittest.mock.patch("HABApp.openhab.interface_sync.create_item", spec=HABApp.openhab.interface_sync.create_item) as create_mock, unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
            habapp_rules.core.helper.create_additional_item("Name_of_Item", "Switch")
            create_mock.assert_not_called()

    def test_test_create_additional_item_exception(self) -> None:
        """Test exceptions of _create_additional_item."""
        self.item_exists_mock.return_value = False
        with unittest.mock.patch("HABApp.openhab.interface_sync.create_item", spec=HABApp.openhab.interface_sync.create_item, return_value=False), self.assertRaises(habapp_rules.core.exceptions.HabAppRulesError):
            habapp_rules.core.helper.create_additional_item("Name_of_Item", "Switch")

    def test_send_if_different(self) -> None:
        """Test send_if_different."""
        # item given
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number", 0)
        number_item = HABApp.openhab.items.NumberItem.get_item("Unittest_Number")

        habapp_rules.core.helper.send_if_different(number_item, 0)
        tests.helper.oh_item.assert_value("Unittest_Number", 0)

        habapp_rules.core.helper.send_if_different(number_item, 42)
        tests.helper.oh_item.assert_value("Unittest_Number", 42)

        # name given
        habapp_rules.core.helper.send_if_different("Unittest_Number", 42)
        tests.helper.oh_item.assert_value("Unittest_Number", 42)

        habapp_rules.core.helper.send_if_different("Unittest_Number", 84)
        tests.helper.oh_item.assert_value("Unittest_Number", 84)


class TestHelperWithItems(tests.helper.test_case_base.TestCaseBase):
    """Test helper functions with OpenHAB items."""

    def test_filter_updated_items(self) -> None:
        """Test filter_updated_items."""
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number", 0)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer", 0)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch", "OFF")

        item_number = HABApp.openhab.items.NumberItem.get_item("Unittest_Number")
        item_dimmer = HABApp.openhab.items.DimmerItem.get_item("Unittest_Dimmer")
        item_switch = HABApp.openhab.items.SwitchItem.get_item("Unittest_Switch")

        # without filter
        result = habapp_rules.core.helper.filter_updated_items([item_number, item_dimmer, item_switch])
        self.assertListEqual([item_number, item_dimmer, item_switch], result)

        # with filter
        result = habapp_rules.core.helper.filter_updated_items([item_number, item_dimmer, item_switch], 60)
        self.assertListEqual([item_number, item_dimmer, item_switch], result)

        item_dimmer._last_update = HABApp.core.items.base_item.UpdatedTime("Unittest_Dimmer", whenever.Instant.from_timestamp(time.time() - 61))
        result = habapp_rules.core.helper.filter_updated_items([item_number, item_dimmer, item_switch], 60)
        self.assertListEqual([item_number, item_switch], result)
