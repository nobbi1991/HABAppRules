"""Test config models of logic rules."""

from HABApp.openhab.items import ContactItem, SwitchItem

from habapp_rules.common.config.logic import BinaryLogicItems
from tests.helper.oh_item import add_mock_item
from tests.helper.test_case_base import TestCaseBase


class TestBinaryLogicItems(TestCaseBase):
    """Test BinaryLogicItems."""

    def tests_model_validator(self) -> None:
        """Tests model_validator."""
        add_mock_item(SwitchItem, "Unittest_Input_Switch", None)
        add_mock_item(ContactItem, "Unittest_Input_Contact", None)
        add_mock_item(SwitchItem, "Unittest_Output_Switch", None)
        add_mock_item(ContactItem, "Unittest_Output_Contact", None)

        # input and output items are the same
        BinaryLogicItems(inputs=["Unittest_Input_Switch"], output="Unittest_Output_Switch")

        BinaryLogicItems(inputs=["Unittest_Input_Contact"], output="Unittest_Output_Contact")

        # input and output items are different
        with self.assertRaises(TypeError):
            BinaryLogicItems(inputs=["Unittest_Input_Switch"], output="Unittest_Output_Contact")

        with self.assertRaises(TypeError):
            BinaryLogicItems(inputs=["Unittest_Input_Contact"], output="Unittest_Output_Switch")
