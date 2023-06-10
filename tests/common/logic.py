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
