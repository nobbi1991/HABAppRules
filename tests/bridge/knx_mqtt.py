"""Test KNX MQTT bridges."""
import collections
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.bridge.knx_mqtt
import tests.helper.oh_item
import tests.helper.rule_runner


# pylint: disable=protected-access
class TestLight(unittest.TestCase):
	"""Tests cases for testing Light rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.send_command_mock_patcher.stop)
		self.send_command_mock = self.send_command_mock_patcher.start()

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_KNX_Dimmer_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_MQTT_dimmer", 0)

		self._knx_bridge = habapp_rules.bridge.knx_mqtt.KnxMqttDimmerBridge("Unittest_KNX_Dimmer_ctr", "Unittest_MQTT_dimmer")

	def test_knx_on_off(self):
		"""Test ON/OFF from KNX"""
		self.assertEqual(0, self._knx_bridge._mqtt_item.value)

		# ON via KNX
		tests.helper.oh_item.item_command_event("Unittest_KNX_Dimmer_ctr", "ON")
		self.assertEqual(100, self._knx_bridge._mqtt_item.value)

		# OFF via KNX
		tests.helper.oh_item.item_command_event("Unittest_KNX_Dimmer_ctr", "OFF")
		self.assertEqual(0, self._knx_bridge._mqtt_item.value)

	def test_knx_value(self):
		"""Test value from KNX"""
		self.assertEqual(0, self._knx_bridge._mqtt_item.value)
		tests.helper.oh_item.item_command_event("Unittest_KNX_Dimmer_ctr", 42)
		self.assertEqual(42, self._knx_bridge._mqtt_item.value)

	def test_knx_increase(self):
		"""Test increase from KNX."""
		self.assertEqual(0, self._knx_bridge._mqtt_item.value)
		tests.helper.oh_item.item_command_event("Unittest_KNX_Dimmer_ctr", "INCREASE")
		self.assertEqual(60, self._knx_bridge._mqtt_item.value)
		tests.helper.oh_item.item_command_event("Unittest_KNX_Dimmer_ctr", "INCREASE")
		self.assertEqual(100, self._knx_bridge._mqtt_item.value)

	def test_knx_decrease(self):
		"""Test decrease from KNX."""
		self._knx_bridge._mqtt_item.oh_send_command(100)
		self.assertEqual(100, self._knx_bridge._mqtt_item.value)
		tests.helper.oh_item.item_command_event("Unittest_KNX_Dimmer_ctr", "DECREASE")
		self.assertEqual(30, self._knx_bridge._mqtt_item.value)
		tests.helper.oh_item.item_command_event("Unittest_KNX_Dimmer_ctr", "DECREASE")
		self.assertEqual(0, self._knx_bridge._mqtt_item.value)

	def test_knx_not_supported(self):
		"""Test not supported command coming from KNX."""
		with unittest.mock.patch("habapp_rules.bridge.knx_mqtt.LOGGER") as logger_mock:
			tests.helper.oh_item.item_command_event("Unittest_KNX_Dimmer_ctr", "NotSupported")
			logger_mock.error.assert_called_once_with("command 'NotSupported' ist not supported!")

	def test_mqtt_events(self):
		"""Test if KNX item is updated correctly if MQTT item changed."""
		self.assertEqual(0, self._knx_bridge._mqtt_item.value)
		TestCase = collections.namedtuple("TestCase", "send_value, expected_calls")

		test_cases = [
			TestCase(70, [unittest.mock.call(70), unittest.mock.call("ON")]),
			TestCase(100, [unittest.mock.call(100)]),
			TestCase(1, [unittest.mock.call(1)]),
			TestCase(0, [unittest.mock.call(0), unittest.mock.call("OFF")])
		]

		with unittest.mock.patch.object(self._knx_bridge, "_knx_item") as knx_item_mock:
			for test_case in test_cases:
				knx_item_mock.oh_post_update.reset_mock()
				tests.helper.oh_item.item_state_change_event("Unittest_MQTT_dimmer", test_case.send_value)
				knx_item_mock.oh_post_update.assert_has_calls(test_case.expected_calls)

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
