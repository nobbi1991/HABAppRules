"""Test notification rules."""

import unittest.mock

from HABApp.openhab.items import OpenhabItem, StringItem, SwitchItem
from multi_notifier.connectors.connector_mail import Mail
from multi_notifier.connectors.connector_telegram import Telegram

from habapp_rules.system.config.notification import NotificationConfig, NotificationItems, NotificationParameter
from habapp_rules.system.notification import SendStateChanged
from tests.helper.oh_item import (
    add_mock_item,
    item_state_change_event,
)
from tests.helper.test_case_base import TestCaseBase


class TestNotification(TestCaseBase):
    """Test class for notification."""

    def setUp(self) -> None:
        """Set up test case."""
        TestCaseBase.setUp(self)

        add_mock_item(StringItem, "Unittest_String", None)
        add_mock_item(SwitchItem, "Unittest_Switch", None)

        self._mail_mock = unittest.mock.MagicMock(spec=Mail)
        self._telegram_mock = unittest.mock.MagicMock(spec=Telegram)

        self._mail_rule = SendStateChanged(NotificationConfig(items=NotificationItems(target_item=OpenhabItem.get_item("Unittest_String")), parameter=NotificationParameter(notify_connector=self._mail_mock, recipients="mock@mail.de")))
        self._telegram_rule = SendStateChanged(NotificationConfig(items=NotificationItems(target_item=OpenhabItem.get_item("Unittest_Switch")), parameter=NotificationParameter(notify_connector=self._telegram_mock, recipients="mock_id")))

    def test_state_changed(self) -> None:
        """Test state changed."""
        self._mail_mock.send_message.assert_not_called()
        self._telegram_mock.send_message.assert_not_called()

        item_state_change_event("Unittest_String", "New value")
        self._mail_mock.send_message.assert_called_once_with("mock@mail.de", "Unittest_String changed from None to New value", subject="Unittest_String changed")

        item_state_change_event("Unittest_String", "Even never value")
        self._mail_mock.send_message.assert_called_with("mock@mail.de", "Unittest_String changed from New value to Even never value", subject="Unittest_String changed")

        item_state_change_event("Unittest_Switch", "ON")
        self._telegram_mock.send_message.assert_called_once_with("mock_id", "Unittest_Switch changed from None to ON")

        item_state_change_event("Unittest_Switch", "OFF")
        self._telegram_mock.send_message.assert_called_with("mock_id", "Unittest_Switch changed from ON to OFF")
