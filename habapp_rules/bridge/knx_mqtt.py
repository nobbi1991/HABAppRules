"""Rules for bridging KNX controller to MQTT items."""
import logging

import HABApp

import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class KnxMqttDimmerBridge(HABApp.Rule):
	"""Create a bridge to control a MQTT dimmer from a KNX controller (e.g. wall switch).

	To use this the items must be configured according the following example:
	- knx_dimmer_ctr: autoupdate must be activated, thing:  [ switch="1/1/124+1/1/120", position="1/1/125+1/1/123", increaseDecrease="1/1/122" ] for switch/position: at first always use the RM-GA, second is the control-GA
	- mqtt_dimmer: autoupdate does not matter, thing: according to OpenHAB documentation

	info: OpenHAB does not support start/stop dimming. Thus, this implementation will set fixed values if INCREASE/DECREASE was received from KNX
	"""

	def __init__(self, knx_dimmer_ctr: str, mqtt_dimmer: str, increase_value: int = 60, decrease_value: int = 30) -> None:
		"""Create object of KNX to MQTT bridge

		:param knx_dimmer_ctr: name of KNX control item
		:param mqtt_dimmer: name of MQTT item
		:param increase_value: value which is set when INCREASE was received.
		:param decrease_value: value which is set when DECREASE was received.
		"""
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, f"{knx_dimmer_ctr}__{mqtt_dimmer}")

		self.__increase_value = increase_value
		self.__decrease_value = decrease_value

		self._knx_item = HABApp.openhab.items.DimmerItem.get_item(knx_dimmer_ctr)
		self._mqtt_item = HABApp.openhab.items.DimmerItem.get_item(mqtt_dimmer)

		self._knx_item.listen_event(self._cb_knx_event, HABApp.openhab.events.ItemCommandEventFilter())
		self._mqtt_item.listen_event(self._cb_mqtt_event, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _cb_knx_event(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is called if a KNX command received.

		:param event: HABApp event
		"""
		if isinstance(event.value, (int, float)):
			self._mqtt_item.oh_send_command(event.value)
		elif event.value in {"ON", "OFF"}:
			self._mqtt_item.oh_send_command(event.value)
		elif event.value == "INCREASE":
			if self._mqtt_item.value < self.__increase_value:
				self._mqtt_item.oh_send_command(self.__increase_value)
			else:
				self._mqtt_item.oh_send_command(100)
		elif event.value == "DECREASE":
			if self._mqtt_item.value > self.__decrease_value:
				self._mqtt_item.oh_send_command(self.__decrease_value)
			else:
				self._mqtt_item.oh_send_command(0)
		else:
			self._instance_logger.error(f"command '{event.value}' ist not supported!")

	def _cb_mqtt_event(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is called if a MQTT state change event happens.

		:param event: HABApp event
		"""
		self._knx_item.oh_post_update(event.value)

		if event.value > 0:
			self._knx_item.oh_post_update("ON")
		else:
			self._knx_item.oh_post_update("OFF")
