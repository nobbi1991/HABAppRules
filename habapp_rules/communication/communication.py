"""Module for communication with Telegram, Mail, ..."""
from __future__ import annotations

import email.mime.text
import json
import logging
import pathlib
import smtplib

import requests

import habapp_rules

LOGGER = logging.getLogger("HABApp.communication")
LOGGER.setLevel("DEBUG")


class Telegram:
	"""Class to send Telegram messages"""

	def __init__(self, bot_token: str, chat_ids: dict) -> None:
		"""Init Telegram class.

		:param bot_token: bot token from telegram
		:param chat_ids: dictionary which holds the mapping between name and chat_id
		"""
		self.__bot_token = bot_token
		self._chat_ids = chat_ids

	@property
	def chat_ids(self) -> dict:
		"""Property holds the current dictionary of known chat ids.

		:return: dictionary of chat ids
		"""
		return self._chat_ids

	def __get_chat_ids(self, recipient_names: list[str]) -> list[str]:
		"""Get chat ids from recipient names.

		:param recipient_names: list of recipient ids to transform
		:return: list of chat ids
		"""
		return [self._chat_ids[name] for name in recipient_names]

	def send_msg(self, msg: str, recipient_names: str | list[str]) -> None:
		"""Send a text message.

		:param msg: message which should be sent
		:param recipient_names: single name or list of names of the recipient (must be part of the chat_ids dict)
		"""
		recipient_names = ensure_is_list(recipient_names)

		for idx in self.__get_chat_ids(recipient_names):
			response = requests.get(f"https://api.telegram.org/bot{self.__bot_token}/sendMessage", params={"chat_id": idx, "parse_mode": "Markdown", "text": msg})
			if not response.ok:
				LOGGER.warning(f"Could not send telegram message '{msg}' to chat_id={idx}")

	def send_picture(self, picture_path: pathlib.Path, recipient_names: str | list[str], msg: str = None) -> None:
		"""Send a picture with optional message

		:param picture_path: file path of picture
		:param recipient_names: single name or list of names of the recipient (must be part of the chat_ids dict)
		:param msg: optional message
		"""
		recipient_names = ensure_is_list(recipient_names)

		with open(picture_path, "rb") as picture:
			for idx in self.__get_chat_ids(recipient_names):
				response = requests.get(f"https://api.telegram.org/bot{self.__bot_token}/sendPhoto", params={"chat_id": idx, "caption": msg}, files={"photo": picture})
				if not response.ok:
					LOGGER.warning(f"Could not send telegram picture to chat_id={idx}")


class Mail:
	"""Class to send e-mails."""

	def __init__(self, user: str, password: str, smtp_host: str, smtp_port: int = 465):
		"""Init Mail class.

		:param user: username to log in to mail account
		:param password: password to log in to mail account
		:param smtp_host: smtp host name (e.g. smtp.1und1.de)
		:param smtp_port: smtp port
		"""
		self.__user = user
		self.__password = password

		self.__smtp_server = smtplib.SMTP_SSL(smtp_host, smtp_port)

	def send_mail(self, recipient: str | list[str], subject: str, msg: str) -> None:
		"""Send a mail to single or multiple recipients

		:param recipient: single or list of recipient (mail address)
		:param subject: subject of mail
		:param msg: message of mail
		"""
		mail_msg = email.mime.text.MIMEText(msg)
		mail_msg["Subject"] = subject
		mail_msg["From"] = self.__user

		self.__smtp_server.ehlo()
		self.__smtp_server.login(self.__user, self.__password)
		self.__smtp_server.sendmail(self.__user, recipient, mail_msg.as_string())
		self.__smtp_server.close()


def ensure_is_list(recipient: str | list[str]) -> list[str]:
	"""Ensure that recipient is a list of strings.

	:param recipient: single or multiple recipients
	:return: list of recipients
	"""
	if isinstance(recipient, str):
		recipient = [recipient]
	return recipient


with open(habapp_rules.BASE_PATH / "rules/communication/communication.json", "r", encoding="utf-8") as config_json:
	__config: dict = json.load(config_json)

# TELEGRAM = Telegram(__config["telegram"]["bot_token"], __config["telegram"]["chat_ids"])
# MAIL = Mail(__config["mail"]["user"], __config["mail"]["password"], __config["mail"]["smtp_host"], __config["mail"]["smtp_port"], )
