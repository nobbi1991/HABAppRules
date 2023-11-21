"""Unit-test for logic functions."""
import collections
import unittest.mock

import HABApp.openhab.items.switch_item

import habapp_rules.common.logic
import habapp_rules.core.state_machine_rule
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.test_case_base


# pylint: disable=protected-access
class TestAndOR(tests.helper.test_case_base.TestCaseBase):
	"""Tests for AND / OR."""

	def setUp(self) -> None:
		"""Setup unit-tests."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		self.post_update_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.post_update", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.post_update_mock_patcher.stop)
		self.post_update_mock_patcher.start()

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_out", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_in1", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_in2", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_in3", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Contact_out", "OPEN")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Contact_in1", "OPEN")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Contact_in2", "OPEN")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Contact_in3", "OPEN")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_String", "")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.RollershutterItem, "Unittest_RollerShutter", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "Unittest_DateTime", 0)

	def test_base_init_exceptions(self):
		"""Test exceptions during init."""
		# unsupported item output type
		for item_name in ["Unittest_Number", "Unittest_Dimmer", "Unittest_String", "Unittest_RollerShutter", "Unittest_DateTime"]:
			with self.assertRaises(TypeError) as context:
				habapp_rules.common.logic.And([item_name], item_name)
			self.assertIn("is not supported. Type must be SwitchItem or ContactItem", str(context.exception))

		# wrong input type
		for item_name in ["Unittest_Number", "Unittest_Dimmer", "Unittest_String", "Unittest_RollerShutter", "Unittest_DateTime"]:
			and_rule = habapp_rules.common.logic.And(["Unittest_Contact_in1", item_name], "Unittest_Contact_out")
			self.assertEqual(["Unittest_Contact_in1"], [itm.name for itm in and_rule._input_items])

	def test_and_callback_switch(self):
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

		habapp_rules.common.logic.And(["Unittest_Switch_in1", "Unittest_Switch_in2", "Unittest_Switch_in3"], "Unittest_Switch_out")
		output_item = HABApp.openhab.items.SwitchItem.get_item("Unittest_Switch_out")

		for step in test_steps:
			tests.helper.oh_item.send_command(step.event_item_name, step.event_item_value)
			self.assertEqual(step.expected_output, output_item.value)

	def test_or_callback_switch(self):
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

		habapp_rules.common.logic.Or(["Unittest_Switch_in1", "Unittest_Switch_in2", "Unittest_Switch_in3"], "Unittest_Switch_out")
		output_item = HABApp.openhab.items.SwitchItem.get_item("Unittest_Switch_out")

		for step in test_steps:
			tests.helper.oh_item.send_command(step.event_item_name, step.event_item_value)
			self.assertEqual(step.expected_output, output_item.value)

	def test_and_callback_contact(self):
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

		habapp_rules.common.logic.And(["Unittest_Contact_in1", "Unittest_Contact_in2", "Unittest_Contact_in3"], "Unittest_Contact_out")
		output_item = HABApp.openhab.items.ContactItem.get_item("Unittest_Contact_out")

		for step in test_steps:
			tests.helper.oh_item.send_command(step.event_item_name, step.event_item_value)
			self.assertEqual(step.expected_output, output_item.value)

	def test_or_callback_contact(self):
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

		habapp_rules.common.logic.Or(["Unittest_Contact_in1", "Unittest_Contact_in2", "Unittest_Contact_in3"], "Unittest_Contact_out")
		output_item = HABApp.openhab.items.ContactItem.get_item("Unittest_Contact_out")

		for step in test_steps:
			tests.helper.oh_item.send_command(step.event_item_name, step.event_item_value)
			self.assertEqual(step.expected_output, output_item.value)


class TestNumericLogic(tests.helper.test_case_base.TestCaseBase):
	"""Tests for And / Or / Sum."""

	def setUp(self) -> None:
		"""Setup unit-tests."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number_out_min", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number_out_max", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number_out_sum", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number_in1", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number_in2", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number_in3", 0)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_out_min", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_out_max", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_in1", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_in2", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_in3", 0)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Contact", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_String", "")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.RollershutterItem, "Unittest_RollerShutter", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DatetimeItem, "Unittest_DateTime", 0)

	def test_base_init_exceptions(self):
		"""Test exceptions during init."""
		# unsupported item output type
		for item_name in ["Unittest_Switch", "Unittest_Contact", "Unittest_String", "Unittest_RollerShutter", "Unittest_DateTime"]:
			with self.assertRaises(TypeError) as context:
				habapp_rules.common.logic.Min([item_name], item_name)
			self.assertIn("is not supported. Type must be NumberItem or DimmerItem", str(context.exception))

		# wrong input type
		for item_name in ["Unittest_Switch", "Unittest_Contact", "Unittest_String", "Unittest_RollerShutter", "Unittest_DateTime"]:
			and_rule = habapp_rules.common.logic.Max(["Unittest_Number_in1", item_name], "Unittest_Number_out_max")
			self.assertEqual(["Unittest_Number_in1"], [itm.name for itm in and_rule._input_items])

	def test_number_min_max_sum_without_filter(self):
		"""Test min / max / sum for number items."""
		TestStep = collections.namedtuple("TestStep", "event_item_index, event_item_value, expected_min, expected_max, expected_sum")

		test_steps = [
			# test change single value
			TestStep(1, 100, 0, 100, 100),
			TestStep(1, 0, 0, 0, 0),
			TestStep(1, -100, -100, 0, -100),

			# change all values to 5000
			TestStep(1, 5000, 0, 5000, 5000),
			TestStep(2, 5000, 0, 5000, 10_000),
			TestStep(3, 5000, 5000, 5000, 15_000),

			# some random values
			TestStep(3, -1000, -1000, 5000, 9000),
			TestStep(3, -500, -500, 5000, 9500),
			TestStep(1, 200, -500, 5000, 4700)
		]

		habapp_rules.common.logic.Min(["Unittest_Number_in1", "Unittest_Number_in2", "Unittest_Number_in3"], "Unittest_Number_out_min")
		habapp_rules.common.logic.Max(["Unittest_Number_in1", "Unittest_Number_in2", "Unittest_Number_in3"], "Unittest_Number_out_max")
		habapp_rules.common.logic.Sum(["Unittest_Number_in1", "Unittest_Number_in2", "Unittest_Number_in3"], "Unittest_Number_out_sum")

		output_item_number_min = HABApp.openhab.items.NumberItem.get_item("Unittest_Number_out_min")
		output_item_number_max = HABApp.openhab.items.NumberItem.get_item("Unittest_Number_out_max")
		output_item_number_sum = HABApp.openhab.items.NumberItem.get_item("Unittest_Number_out_sum")

		for step in test_steps:
			tests.helper.oh_item.item_state_change_event(f"Unittest_Number_in{step.event_item_index}", step.event_item_value)

			self.assertEqual(step.expected_min, output_item_number_min.value)
			self.assertEqual(step.expected_max, output_item_number_max.value)
			self.assertEqual(step.expected_sum, output_item_number_sum.value)

	def test_dimmer_min_max_without_filter(self):
		"""Test min / max for dimmer items."""
		TestStep = collections.namedtuple("TestStep", "event_item_index, event_item_value, expected_min, expected_max")

		test_steps = [
			# test change single value
			TestStep(1, 100, 0, 100),
			TestStep(1, 0, 0, 0),
			TestStep(1, 50, 0, 50),

			# change all values to 80
			TestStep(1, 80, 0, 80),
			TestStep(2, 80, 0, 80),
			TestStep(3, 80, 80, 80),

			# some random values
			TestStep(3, 1, 1, 80),
			TestStep(3, 20, 20, 80),
			TestStep(1, 50, 20, 80)
		]

		habapp_rules.common.logic.Min(["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], "Unittest_Dimmer_out_min")
		habapp_rules.common.logic.Max(["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], "Unittest_Dimmer_out_max")
		output_item_dimmer_min = HABApp.openhab.items.DimmerItem.get_item("Unittest_Dimmer_out_min")
		output_item_dimmer_max = HABApp.openhab.items.DimmerItem.get_item("Unittest_Dimmer_out_max")

		for step in test_steps:
			tests.helper.oh_item.item_state_change_event(f"Unittest_Dimmer_in{step.event_item_index}", step.event_item_value)

			self.assertEqual(step.expected_min, output_item_dimmer_min.value)
			self.assertEqual(step.expected_max, output_item_dimmer_max.value)

	def test_cb_input_event(self):
		"""Test _cb_input_event."""
		rule_min = habapp_rules.common.logic.Min(["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], "Unittest_Dimmer_out_min")
		rule_max = habapp_rules.common.logic.Max(["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], "Unittest_Dimmer_out_max")

		with unittest.mock.patch("habapp_rules.core.helper.filter_updated_items", return_value=[None]), unittest.mock.patch.object(rule_min, "_set_output_state") as set_output_mock:
			rule_min._cb_input_event(None)
		set_output_mock.assert_not_called()

		with unittest.mock.patch("habapp_rules.core.helper.filter_updated_items", return_value=[None]), unittest.mock.patch.object(rule_max, "_set_output_state") as set_output_mock:
			rule_max._cb_input_event(None)
		set_output_mock.assert_not_called()

	def test_exception_dimmer_sum(self):
		"""Test exception if Sum is instantiated with dimmer items."""
		with self.assertRaises(TypeError):
			habapp_rules.common.logic.Sum(["Unittest_Dimmer_in1", "Unittest_Dimmer_in2", "Unittest_Dimmer_in3"], "Unittest_Dimmer_out_max")
