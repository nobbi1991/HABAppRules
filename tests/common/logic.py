"""Unit-test for logic functions."""

import collections
import unittest.mock

from HABApp.openhab.items import ContactItem, DatetimeItem, DimmerItem, NumberItem, RollershutterItem, StringItem, SwitchItem

from habapp_rules.common.config.logic import BinaryLogicConfig, BinaryLogicItems, InvertValueConfig, InvertValueItems, InvertValueParameter, NumericLogicConfig, NumericLogicItems
from habapp_rules.common.logic import And, InvertValue, Max, Min, Or, Sum
from tests.helper.oh_item import add_mock_item, assert_item_value, item_state_change_event, send_command
from tests.helper.test_case_base import TestCaseBase


class TestAndOR(TestCaseBase):
    """Tests for AND / OR."""

    def setUp(self) -> None:
        """Setup unit-tests."""
        TestCaseBase.setUp(self)

        add_mock_item(SwitchItem, "Unittest_Switch_out", None)
        add_mock_item(SwitchItem, "Unittest_Switch_in1", None)
        add_mock_item(SwitchItem, "Unittest_Switch_in2", None)
        add_mock_item(SwitchItem, "Unittest_Switch_in3", None)

        add_mock_item(ContactItem, "Unittest_Contact_out", None)
        add_mock_item(ContactItem, "Unittest_Contact_in1", None)
        add_mock_item(ContactItem, "Unittest_Contact_in2", None)
        add_mock_item(ContactItem, "Unittest_Contact_in3", None)

        add_mock_item(NumberItem, "Unittest_Number", None)
        add_mock_item(DimmerItem, "Unittest_Dimmer", None)
        add_mock_item(StringItem, "Unittest_String", None)
        add_mock_item(RollershutterItem, "Unittest_RollerShutter", None)
        add_mock_item(DatetimeItem, "Unittest_DateTime", None)

    def test_and_callback_switch(self) -> None:
        """Test <AND> for switch items."""
        TestStep = collections.namedtuple("TestStep", "event_item_name, event_item_value, expected_output")

        test_steps = [
            # test toggle of one switch
            TestStep("Unittest_Switch_in1", "ON", "OFF"),
            TestStep("Unittest_Switch_in1", "OFF", "OFF"),
            # switch on all
            TestStep("Unittest_Switch_in1", "ON", "OFF"),
            TestStep("Unittest_Switch_in2", "ON", "OFF"),
            TestStep("Unittest_Switch_in3", "ON", "ON"),
            # toggle one switch
            TestStep("Unittest_Switch_in1", "OFF", "OFF"),
            TestStep("Unittest_Switch_in1", "ON", "ON"),
            # switch off all
            TestStep("Unittest_Switch_in2", "OFF", "OFF"),
            TestStep("Unittest_Switch_in1", "OFF", "OFF"),
            TestStep("Unittest_Switch_in3", "OFF", "OFF"),
        ]

        config = BinaryLogicConfig(items=BinaryLogicItems(inputs=["Unittest_Switch_in1", "Unittest_Switch_in2", "Unittest_Switch_in3"], output="Unittest_Switch_out"))

        And(config)
        output_item = SwitchItem.get_item("Unittest_Switch_out")

        for step in test_steps:
            send_command(step.event_item_name, step.event_item_value)
            self.assertEqual(step.expected_output, output_item.value)

    def test_or_callback_switch(self) -> None:
        """Test <OR> for switch items."""
        TestStep = collections.namedtuple("TestStep", "event_item_name, event_item_value, expected_output")

        test_steps = [
            # test toggle of one switch
            TestStep("Unittest_Switch_in1", "ON", "ON"),
            TestStep("Unittest_Switch_in1", "OFF", "OFF"),
            # switch on all
            TestStep("Unittest_Switch_in1", "ON", "ON"),
            TestStep("Unittest_Switch_in2", "ON", "ON"),
            TestStep("Unittest_Switch_in3", "ON", "ON"),
            # toggle one switch
            TestStep("Unittest_Switch_in1", "OFF", "ON"),
            TestStep("Unittest_Switch_in1", "ON", "ON"),
            # switch off all
            TestStep("Unittest_Switch_in2", "OFF", "ON"),
            TestStep("Unittest_Switch_in1", "OFF", "ON"),
            TestStep("Unittest_Switch_in3", "OFF", "OFF"),
        ]

        config = BinaryLogicConfig(items=BinaryLogicItems(inputs=["Unittest_Switch_in1", "Unittest_Switch_in2", "Unittest_Switch_in3"], output="Unittest_Switch_out"))

        Or(config)
        output_item = SwitchItem.get_item("Unittest_Switch_out")

        for step in test_steps:
            send_command(step.event_item_name, step.event_item_value)
            self.assertEqual(step.expected_output, output_item.value)

    def test_and_callback_contact(self) -> None:
        """Test <AND> for contact items."""
        TestStep = collections.namedtuple("TestStep", "event_item_name, event_item_value, expected_output")

        test_steps = [
            # test toggle of one Contact
            TestStep("Unittest_Contact_in1", "CLOSED", "OPEN"),
            TestStep("Unittest_Contact_in1", "OPEN", "OPEN"),
            # Contact on all
            TestStep("Unittest_Contact_in1", "CLOSED", "OPEN"),
            TestStep("Unittest_Contact_in2", "CLOSED", "OPEN"),
            TestStep("Unittest_Contact_in3", "CLOSED", "CLOSED"),
            # toggle one Contact
            TestStep("Unittest_Contact_in1", "OPEN", "OPEN"),
            TestStep("Unittest_Contact_in1", "CLOSED", "CLOSED"),
            # Contact off all
            TestStep("Unittest_Contact_in2", "OPEN", "OPEN"),
            TestStep("Unittest_Contact_in1", "OPEN", "OPEN"),
            TestStep("Unittest_Contact_in3", "OPEN", "OPEN"),
        ]

        config = BinaryLogicConfig(items=BinaryLogicItems(inputs=["Unittest_Contact_in1", "Unittest_Contact_in2", "Unittest_Contact_in3"], output="Unittest_Contact_out"))

        And(config)
        output_item = ContactItem.get_item("Unittest_Contact_out")

        for step in test_steps:
            send_command(step.event_item_name, step.event_item_value)
            self.assertEqual(step.expected_output, output_item.value)

    def test_or_callback_contact(self) -> None:
        """Test <or> for contact items."""
        TestStep = collections.namedtuple("TestStep", "event_item_name, event_item_value, expected_output")

        test_steps = [
            # test toggle of one Contact
            TestStep("Unittest_Contact_in1", "CLOSED", "CLOSED"),
            TestStep("Unittest_Contact_in1", "OPEN", "OPEN"),
            # Contact on all
            TestStep("Unittest_Contact_in1", "CLOSED", "CLOSED"),
            TestStep("Unittest_Contact_in2", "CLOSED", "CLOSED"),
            TestStep("Unittest_Contact_in3", "CLOSED", "CLOSED"),
            # toggle one Contact
            TestStep("Unittest_Contact_in1", "OPEN", "CLOSED"),
            TestStep("Unittest_Contact_in1", "CLOSED", "CLOSED"),
            # Contact off all
            TestStep("Unittest_Contact_in2", "OPEN", "CLOSED"),
            TestStep("Unittest_Contact_in1", "OPEN", "CLOSED"),
            TestStep("Unittest_Contact_in3", "OPEN", "OPEN"),
        ]

        config = BinaryLogicConfig(items=BinaryLogicItems(inputs=["Unittest_Contact_in1", "Unittest_Contact_in2", "Unittest_Contact_in3"], output="Unittest_Contact_out"))

        Or(config)
        output_item = ContactItem.get_item("Unittest_Contact_out")

        for step in test_steps:
            send_command(step.event_item_name, step.event_item_value)
            self.assertEqual(step.expected_output, output_item.value)


class TestNumericLogic(TestCaseBase):
    """Tests Numeric logic rules."""

    def setUp(self) -> None:
        """Setup unit-tests."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Number_out_min", None)
        add_mock_item(NumberItem, "Unittest_Number_out_max", None)
        add_mock_item(NumberItem, "Unittest_Number_out_sum", None)

        add_mock_item(NumberItem, "Unittest_Number_in1", None)
        add_mock_item(NumberItem, "Unittest_Number_in2", None)
        add_mock_item(NumberItem, "Unittest_Number_in3", None)

        add_mock_item(DimmerItem, "Unittest_Dimmer_out_min", None)
        add_mock_item(DimmerItem, "Unittest_Dimmer_out_max", None)

        add_mock_item(DimmerItem, "Unittest_Dimmer_in1", None)
        add_mock_item(DimmerItem, "Unittest_Dimmer_in2", None)
        add_mock_item(DimmerItem, "Unittest_Dimmer_in3", None)

        add_mock_item(SwitchItem, "Unittest_Switch", None)
        add_mock_item(ContactItem, "Unittest_Contact", None)
        add_mock_item(StringItem, "Unittest_String", None)
        add_mock_item(RollershutterItem, "Unittest_RollerShutter", None)
        add_mock_item(DatetimeItem, "Unittest_DateTime", None)

    def test_number_min_max_sum_without_filter(self) -> None:
        """Test min / max / sum for number items."""
        TestStep = collections.namedtuple("TestStep", "event_item_index, event_item_value, expected_min, expected_max, expected_sum")

        test_steps = [
            # test change single value
            TestStep(1, 100, 100, 100, 100),
            TestStep(1, 0, 0, 0, 0),
            TestStep(1, -100, -100, -100, -100),
            # change all values to 5000
            TestStep(1, 5000, 5000, 5000, 5000),
            TestStep(2, 5000, 5000, 5000, 10_000),
            TestStep(3, 5000, 5000, 5000, 15_000),
            # some random values
            TestStep(3, -1000, -1000, 5000, 9000),
            TestStep(3, -500, -500, 5000, 9500),
            TestStep(1, 200, -500, 5000, 4700),
        ]

        config_min = NumericLogicConfig(items=NumericLogicItems(inputs=["Unittest_Number_in1", "Unittest_Number_in2", "Unittest_Number_in3"], output="Unittest_Number_out_min"))

        config_max = NumericLogicConfig(items=NumericLogicItems(inputs=["Unittest_Number_in1", "Unittest_Number_in2", "Unittest_Number_in3"], output="Unittest_Number_out_max"))

        config_sum = NumericLogicConfig(items=NumericLogicItems(inputs=["Unittest_Number_in1", "Unittest_Number_in2", "Unittest_Number_in3"], output="Unittest_Number_out_sum"))

        Min(config_min)
        Max(config_max)
        Sum(config_sum)

        output_item_number_min = NumberItem.get_item("Unittest_Number_out_min")
        output_item_number_max = NumberItem.get_item("Unittest_Number_out_max")
        output_item_number_sum = NumberItem.get_item("Unittest_Number_out_sum")

        for step in test_steps:
            item_state_change_event(f"Unittest_Number_in{step.event_item_index}", step.event_item_value)

            self.assertEqual(step.expected_min, output_item_number_min.value)
            self.assertEqual(step.expected_max, output_item_number_max.value)
            self.assertEqual(step.expected_sum, output_item_number_sum.value)

    def test_dimmer_min_max_without_filter(self) -> None:
        """Test min / max for dimmer items."""
        TestStep = collections.namedtuple("TestStep", "event_item_index, event_item_value, expected_min, expected_max")

        test_steps = [
            # test change single value
            TestStep(1, 100, 100, 100),
            TestStep(1, 0, 0, 0),
            TestStep(1, 50, 50, 50),
            # change all values to 80
            TestStep(1, 80, 80, 80),
            TestStep(2, 80, 80, 80),
            TestStep(3, 80, 80, 80),
            # some random values
            TestStep(3, 1, 1, 80),
            TestStep(3, 20, 20, 80),
            TestStep(1, 50, 20, 80),
        ]

        config_min = NumericLogicConfig(items=NumericLogicItems(inputs=["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], output="Unittest_Dimmer_out_min"))

        config_max = NumericLogicConfig(items=NumericLogicItems(inputs=["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], output="Unittest_Dimmer_out_max"))

        Min(config_min)
        Max(config_max)

        output_item_dimmer_min = DimmerItem.get_item("Unittest_Dimmer_out_min")
        output_item_dimmer_max = DimmerItem.get_item("Unittest_Dimmer_out_max")

        for step in test_steps:
            item_state_change_event(f"Unittest_Dimmer_in{step.event_item_index}", step.event_item_value)

            self.assertEqual(step.expected_min, output_item_dimmer_min.value)
            self.assertEqual(step.expected_max, output_item_dimmer_max.value)

    def test_cb_input_event(self) -> None:
        """Test _cb_input_event."""
        config_min = NumericLogicConfig(items=NumericLogicItems(inputs=["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], output="Unittest_Dimmer_out_min"))

        config_max = NumericLogicConfig(items=NumericLogicItems(inputs=["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], output="Unittest_Dimmer_out_max"))

        rule_min = Min(config_min)
        rule_max = Max(config_max)

        with unittest.mock.patch("habapp_rules.core.helper.filter_updated_items", return_value=[None]), unittest.mock.patch.object(rule_min, "_set_output_state") as set_output_mock:
            rule_min._cb_input_event(None)
        set_output_mock.assert_not_called()

        with unittest.mock.patch("habapp_rules.core.helper.filter_updated_items", return_value=[None]), unittest.mock.patch.object(rule_max, "_set_output_state") as set_output_mock:
            rule_max._cb_input_event(None)
        set_output_mock.assert_not_called()

    def test_exception_dimmer_sum(self) -> None:
        """Test exception if Sum is instantiated with dimmer items."""
        config_max = NumericLogicConfig(items=NumericLogicItems(inputs=["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], output="Unittest_Dimmer_out_max"))

        with self.assertRaises(TypeError):
            Sum(config_max)


class TestInvertValue(TestCaseBase):
    """Tests InvertValue rule."""

    def setUp(self) -> None:
        """Setup unit-tests."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Input", None)
        add_mock_item(NumberItem, "Unittest_Output", None)

    def test_invert_value_without_pos_neg(self) -> None:
        """Test invert value rule without pos / neg set."""
        TestCase = collections.namedtuple("TestCase", "input, expected_output")

        test_cases = [TestCase(10, -10), TestCase(1, -1), TestCase(0.1, -0.1), TestCase(0, 0), TestCase(-0.1, 0.1), TestCase(-1, 1), TestCase(-10, 10)]

        config = InvertValueConfig(items=InvertValueItems(input="Unittest_Input", output="Unittest_Output"))

        InvertValue(config)

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                item_state_change_event("Unittest_Input", test_case.input)
                assert_item_value("Unittest_Output", test_case.expected_output)

    def test_invert_value_with_only_pos(self) -> None:
        """Test invert value rule with only pos is set."""
        TestCase = collections.namedtuple("TestCase", "input, expected_output")

        test_cases = [TestCase(10, 0), TestCase(1, 0), TestCase(0.1, 0), TestCase(0, 0), TestCase(-0.1, 0.1), TestCase(-1, 1), TestCase(-10, 10)]

        config = InvertValueConfig(items=InvertValueItems(input="Unittest_Input", output="Unittest_Output"), parameter=InvertValueParameter(only_positive=True))

        InvertValue(config)

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                item_state_change_event("Unittest_Input", test_case.input)
                assert_item_value("Unittest_Output", test_case.expected_output)

    def test_invert_value_with_only_neg(self) -> None:
        """Test invert value rule with only neg is set."""
        TestCase = collections.namedtuple("TestCase", "input, expected_output")

        test_cases = [TestCase(10, -10), TestCase(1, -1), TestCase(0.1, -0.1), TestCase(0, 0), TestCase(-0.1, 0), TestCase(-1, 0), TestCase(-10, 0)]

        config = InvertValueConfig(items=InvertValueItems(input="Unittest_Input", output="Unittest_Output"), parameter=InvertValueParameter(only_negative=True))

        InvertValue(config)

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                item_state_change_event("Unittest_Input", test_case.input)
                assert_item_value("Unittest_Output", test_case.expected_output)
