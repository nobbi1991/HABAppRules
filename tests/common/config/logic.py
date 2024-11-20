"""Test config models of logic rules."""

import HABApp

import habapp_rules.common.config.logic
import tests.helper.oh_item
import tests.helper.test_case_base


class TestBinaryLogicItems(tests.helper.test_case_base.TestCaseBase):
    """Test BinaryLogicItems."""

    def tests_model_validator(self) -> None:
        """Tests model_validator."""
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Input_Switch", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Input_Contact", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output_Switch", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Output_Contact", None)

        # input and output items are the same
        habapp_rules.common.config.logic.BinaryLogicItems(inputs=["Unittest_Input_Switch"], output="Unittest_Output_Switch")

        habapp_rules.common.config.logic.BinaryLogicItems(inputs=["Unittest_Input_Contact"], output="Unittest_Output_Contact")

        # input and output items are different
        with self.assertRaises(TypeError):
            habapp_rules.common.config.logic.BinaryLogicItems(inputs=["Unittest_Input_Switch"], output="Unittest_Output_Contact")

        with self.assertRaises(TypeError):
            habapp_rules.common.config.logic.BinaryLogicItems(inputs=["Unittest_Input_Contact"], output="Unittest_Output_Switch")
