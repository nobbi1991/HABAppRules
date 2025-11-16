"""Test pydantic base models."""

import unittest.mock

import HABApp
import pydantic

import habapp_rules.core.exceptions
import habapp_rules.core.pydantic_base
import tests.helper.oh_item
import tests.helper.test_case_base


class ItemsForTesting(habapp_rules.core.pydantic_base.ItemBase):
    """Items for testing."""

    switch: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="switch item for testing")
    switch_create: HABApp.openhab.items.SwitchItem = pydantic.Field(..., description="switch item for testing", json_schema_extra={"create_if_not_exists": True})
    dimmer_list: list[HABApp.openhab.items.DimmerItem] = pydantic.Field(..., description="list of dimmer items for testing")
    optional_contact: HABApp.openhab.items.ContactItem | None = pydantic.Field(None, description="optional contact item for testing")
    not_supported: HABApp.openhab.items.NumberItem = pydantic.Field(..., description="not supported item for testing")
    thing_item: HABApp.openhab.items.Thing = pydantic.Field(..., description="thing item for testing")


class ItemsListCreateException(habapp_rules.core.pydantic_base.ItemBase):
    """Model with list object where create_if_not_exists is set."""

    some_items: list[HABApp.openhab.items.SwitchItem | HABApp.openhab.items.DimmerItem] = pydantic.Field(..., description="list of items for testing", json_schema_extra={"create_if_not_exists": True})


class WrongTypeException(habapp_rules.core.pydantic_base.ItemBase):
    """Model with wrong type."""

    item: str = pydantic.Field(..., description="wrong type for testing")


class MultipleTypeForCreateException(habapp_rules.core.pydantic_base.ItemBase):
    """Model with multiple types where create_if_not_exists is set."""

    item: HABApp.openhab.items.SwitchItem | HABApp.openhab.items.DimmerItem = pydantic.Field(..., description="list of items for testing", json_schema_extra={"create_if_not_exists": True})


class TestItemBase(tests.helper.test_case_base.TestCaseBase):
    """Test ItemBase."""

    def test_check_all_fields_oh_items_exceptions(self) -> None:
        """Test all exceptions of check_all_fields_oh_items."""
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            ItemsListCreateException(some_items=["Name1", "Name2"])

        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            WrongTypeException(item="Name1")

        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            MultipleTypeForCreateException(item="Name1")

    def test_convert_to_oh_item(self) -> None:
        """Test convert_to_oh_item."""
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number", None)
        tests.helper.oh_item.add_mock_thing("Unittest:Thing")

        dimmer = HABApp.openhab.items.DimmerItem.get_item("Unittest_Dimmer_2")

        # good case
        with unittest.mock.patch("habapp_rules.core.helper.create_additional_item", return_value=HABApp.openhab.items.SwitchItem("Unittest_Switch_Created", "")) as create_item_mock:
            items_for_testing = ItemsForTesting(
                switch="Unittest_Switch",  # normal case
                switch_create="Unittest_Switch_Created",  # item which will be created
                dimmer_list=["Unittest_Dimmer_1", dimmer],  # mixed list of strings and HABApp.openhab.items.DimmerItem
                optional_contact=None,  # test if None is OK
                not_supported="Unittest_Number",  # this causes an exception
                thing_item="Unittest:Thing",  # thing item
            )

        self.assertIsInstance(items_for_testing.switch, HABApp.openhab.items.SwitchItem)
        self.assertIsInstance(items_for_testing.switch_create, HABApp.openhab.items.SwitchItem)
        self.assertIsInstance(items_for_testing.dimmer_list[0], HABApp.openhab.items.DimmerItem)
        self.assertIsInstance(items_for_testing.dimmer_list[1], HABApp.openhab.items.DimmerItem)
        self.assertIsInstance(items_for_testing.not_supported, HABApp.openhab.items.NumberItem)
        self.assertIsInstance(items_for_testing.thing_item, HABApp.openhab.items.Thing)

        self.assertEqual("Unittest_Switch", items_for_testing.switch.name)
        self.assertEqual("Unittest_Switch_Created", items_for_testing.switch_create.name)
        self.assertEqual("Unittest_Dimmer_1", items_for_testing.dimmer_list[0].name)
        self.assertEqual("Unittest_Dimmer_2", items_for_testing.dimmer_list[1].name)
        self.assertEqual("Unittest_Number", items_for_testing.not_supported.name)
        self.assertEqual("Unittest:Thing", items_for_testing.thing_item.name)

        create_item_mock.assert_called_once_with("Unittest_Switch_Created", "Switch")

        # with exception
        with (
            unittest.mock.patch("habapp_rules.core.helper.create_additional_item", return_value=HABApp.openhab.items.SwitchItem("Unittest_Switch_Created", "")) as create_item_mock,
            self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError),
        ):
            ItemsForTesting(
                switch="Unittest_Switch",  # normal case
                switch_create="Unittest_Switch_Created",  # item which will be created
                dimmer_list=["Unittest_Dimmer_1", dimmer],  # mixed list of strings and HABApp.openhab.items.DimmerItem
                optional_contact=None,  # test if None is OK
                not_supported=5,  # this causes an exception
                thing_item="Unittest:Thing",  # thing item
            )

        create_item_mock.assert_called_once_with("Unittest_Switch_Created", "Switch")
