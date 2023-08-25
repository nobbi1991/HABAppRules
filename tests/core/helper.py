"""Unit tests for habapp_rules helper."""
import collections
import unittest
import unittest.mock

import HABApp

import habapp_rules.core.exceptions
import habapp_rules.core.helper
import habapp_rules.core.logger

class TestHelperFunctions(unittest.TestCase):
	"""Tests for all helper functions"""

	def test_create_additional_item(self):
		"""Test create additional item."""
		# check if item is created if NOT existing
		TestCase = collections.namedtuple("TestCase", "item_type, name, label_input, label_call")

		test_cases = [
			TestCase("Switch", "Item_name", "Some label", "Some label"),
			TestCase("Switch", "Item_name", None, "Item name"),
			TestCase("String", "Item_name", "Some label [%s]", "Some label [%s]"),
			TestCase("String", "Item_name", "Some label", "Some label [%s]"),
			TestCase("String", "Item_name", None, "Item name [%s]")
		]

		with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", spec=HABApp.openhab.interface_sync.item_exists, return_value=False), \
				unittest.mock.patch("HABApp.openhab.interface_sync.create_item", spec=HABApp.openhab.interface_sync.create_item) as create_mock, \
				unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
			for test_case in test_cases:
				create_mock.reset_mock()
				habapp_rules.core.helper.create_additional_item(test_case.name, test_case.item_type, test_case.label_input)
				create_mock.assert_called_once_with(item_type=test_case.item_type, name=f"H_{test_case.name}", label=test_case.label_call)

		# check if item is NOT created if existing
		with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", spec=HABApp.openhab.interface_sync.item_exists, return_value=True), \
				unittest.mock.patch("HABApp.openhab.interface_sync.create_item", spec=HABApp.openhab.interface_sync.create_item) as create_mock, \
				unittest.mock.patch("HABApp.openhab.items.OpenhabItem.get_item"):
			habapp_rules.core.helper.create_additional_item("Name_of_Item", "Switch")
			create_mock.assert_not_called()

	def test_test_create_additional_item_exception(self):
		"""Test exceptions of _create_additional_item."""
		with unittest.mock.patch("HABApp.openhab.interface_sync.item_exists", spec=HABApp.openhab.interface_sync.item_exists, return_value=False), \
				unittest.mock.patch("HABApp.openhab.interface_sync.create_item", spec=HABApp.openhab.interface_sync.create_item, return_value=False), \
				self.assertRaises(habapp_rules.core.exceptions.HabAppRulesException):
			habapp_rules.core.helper.create_additional_item("Name_of_Item", "Switch")
