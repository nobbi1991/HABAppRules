"""Test notification rules."""
import unittest.mock

import HABApp.openhab.items
import multi_notifier.connectors.connector_mail
import multi_notifier.connectors.connector_telegram

import habapp_rules.system.notification
import tests.helper.oh_item
import tests.helper.test_case_base


class TestNotification(tests.helper.test_case_base.TestCaseBase):
	"""Test class for notification"""

	def setUp(self):
		"""Set up test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_String", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch", None)

		self._mail_mock = unittest.mock.MagicMock(spec=multi_notifier.connectors.connector_mail.Mail)
		self._telegram_mock = unittest.mock.MagicMock(spec=multi_notifier.connectors.connector_telegram.Telegram)

		self._mail_rule = habapp_rules.system.notification.SendStateChanged("Unittest_String", self._mail_mock, "mock@mail.de")
		self._telegram_rule = habapp_rules.system.notification.SendStateChanged("Unittest_Switch", self._telegram_mock, "mock_id")

	def test_state_changed(self):
		"""Test state changed."""
		self._mail_mock.send_message.assert_not_called()
		self._telegram_mock.send_message.assert_not_called()

		tests.helper.oh_item.item_state_change_event("Unittest_String", "New value")
		self._mail_mock.send_message.assert_called_once_with("mock@mail.de", "Unittest_String changed from None to New value", subject="Unittest_String changed")

		tests.helper.oh_item.item_state_change_event("Unittest_String", "Even never value")
		self._mail_mock.send_message.assert_called_with("mock@mail.de", "Unittest_String changed from New value to Even never value", subject="Unittest_String changed")

		tests.helper.oh_item.item_state_change_event("Unittest_Switch", "ON")
		self._telegram_mock.send_message.assert_called_once_with("mock_id", "Unittest_Switch changed from None to ON")

		tests.helper.oh_item.item_state_change_event("Unittest_Switch", "OFF")
		self._telegram_mock.send_message.assert_called_with("mock_id", "Unittest_Switch changed from ON to OFF")
