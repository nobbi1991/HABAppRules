"""Test pydantic base models."""

import unittest.mock

import pydantic
from HABApp.openhab.items import ContactItem, DimmerItem, NumberItem, SwitchItem, Thing

from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.core.pydantic_base import ItemBase
from tests.helper.oh_item import add_mock_item, add_mock_thing
from tests.helper.test_case_base import TestCaseBase


class ItemsForTesting(ItemBase):
    """Items for testing."""

    switch: SwitchItem = pydantic.Field(..., description="switch item for testing")
    switch_create: SwitchItem = pydantic.Field(..., description="switch item for testing", json_schema_extra={"create_if_not_exists": True})
    dimmer_list: list[DimmerItem] = pydantic.Field(..., description="list of dimmer items for testing")
    optional_contact: ContactItem | None = pydantic.Field(None, description="optional contact item for testing")
    not_supported: NumberItem = pydantic.Field(..., description="not supported item for testing")
    thing_item: Thing = pydantic.Field(..., description="thing item for testing")


class CallableTypeException(ItemBase):
    """Model with callable type."""

    item: SwitchItem = pydantic.Field(..., description="callable for testing", json_schema_extra=print)


class TestItemBase(TestCaseBase):
    """Test ItemBase."""

    def test_check_all_fields_oh_items_exceptions(self) -> None:
        """Test all exceptions of check_all_fields_oh_items."""

        class ItemsListCreateException(ItemBase):
            """Model with list object where create_if_not_exists is set."""

            some_items: list[SwitchItem | DimmerItem] = pydantic.Field(..., description="list of items for testing", json_schema_extra={"create_if_not_exists": True})

        class WrongTypeException(ItemBase):
            """Model with wrong type."""

            item: str = pydantic.Field(..., description="wrong type for testing")

        class MultipleTypeForCreateException(ItemBase):
            """Model with multiple types where create_if_not_exists is set."""

            item: SwitchItem | DimmerItem = pydantic.Field(..., description="list of items for testing", json_schema_extra={"create_if_not_exists": True})

        with self.assertRaises(HabAppRulesConfigurationError):
            ItemsListCreateException(some_items=["Name1", "Name2"])

        with self.assertRaises(HabAppRulesConfigurationError):
            WrongTypeException(item="Name1")

        with self.assertRaises(HabAppRulesConfigurationError):
            MultipleTypeForCreateException(item="Name1")

        with self.assertRaises(HabAppRulesConfigurationError):
            CallableTypeException(item="Name1")

    def test_convert_to_oh_item(self) -> None:
        """Test convert_to_oh_item."""
        add_mock_item(SwitchItem, "Unittest_Switch", None)
        add_mock_item(DimmerItem, "Unittest_Dimmer_1", None)
        add_mock_item(DimmerItem, "Unittest_Dimmer_2", None)
        add_mock_item(NumberItem, "Unittest_Number", None)
        add_mock_thing("Unittest:Thing")

        dimmer = DimmerItem.get_item("Unittest_Dimmer_2")

        # good case
        with unittest.mock.patch("habapp_rules.core.pydantic_base.create_additional_item", return_value=SwitchItem("Unittest_Switch_Created", "")) as create_item_mock:
            items_for_testing = ItemsForTesting(
                switch="Unittest_Switch",  # normal case
                switch_create="Unittest_Switch_Created",  # item which will be created
                dimmer_list=["Unittest_Dimmer_1", dimmer],  # mixed list of strings and DimmerItem
                optional_contact=None,  # test if None is OK
                not_supported="Unittest_Number",  # this causes an exception
                thing_item="Unittest:Thing",  # thing item
            )

        self.assertIsInstance(items_for_testing.switch, SwitchItem)
        self.assertIsInstance(items_for_testing.switch_create, SwitchItem)
        self.assertIsInstance(items_for_testing.dimmer_list[0], DimmerItem)
        self.assertIsInstance(items_for_testing.dimmer_list[1], DimmerItem)
        self.assertIsInstance(items_for_testing.not_supported, NumberItem)
        self.assertIsInstance(items_for_testing.thing_item, Thing)

        self.assertEqual("Unittest_Switch", items_for_testing.switch.name)
        self.assertEqual("Unittest_Switch_Created", items_for_testing.switch_create.name)
        self.assertEqual("Unittest_Dimmer_1", items_for_testing.dimmer_list[0].name)
        self.assertEqual("Unittest_Dimmer_2", items_for_testing.dimmer_list[1].name)
        self.assertEqual("Unittest_Number", items_for_testing.not_supported.name)
        self.assertEqual("Unittest:Thing", items_for_testing.thing_item.name)

        create_item_mock.assert_called_once_with("Unittest_Switch_Created", SwitchItem)

        # with exception
        with (
            unittest.mock.patch("habapp_rules.core.pydantic_base.create_additional_item", return_value=SwitchItem("Unittest_Switch_Created", "")) as create_item_mock,
            self.assertRaises(HabAppRulesConfigurationError),
        ):
            ItemsForTesting(
                switch="Unittest_Switch",  # normal case
                switch_create="Unittest_Switch_Created",  # item which will be created
                dimmer_list=["Unittest_Dimmer_1", dimmer],  # mixed list of strings and DimmerItem
                optional_contact=None,  # test if None is OK
                not_supported=5,  # this causes an exception
                thing_item="Unittest:Thing",  # thing item
            )

        create_item_mock.assert_called_once_with("Unittest_Switch_Created", SwitchItem)
