"""Rules for bridging KNX controller to MQTT items."""
import logging

import HABApp

import habapp_rules.core.exceptions
import habapp_rules.core.logger

LOGGER = logging.getLogger(__name__)


class KnxMqttDimmerBridge(HABApp.Rule):
	"""Create a bridge to control a MQTT dimmer from a KNX controller (e.g. wall switch).

	To use this the items must be configured according the following example:
	- mqtt_dimmer: autoupdate should be false, thing: according to OpenHAB documentation
	- knx_switch_ctr: autoupdate must be activated, thing:  [ ga="1/1/124+1/1/120" ] for ga: at first always use the RM-GA, second is the control-GA
	- knx_dimmer_ctr: autoupdate must be activated, thing:  [ position="1/1/125+1/1/123", increaseDecrease="1/1/122" ] for position: at first always use the RM-GA, second is the control-GA

	info: OpenHAB does not support start/stop dimming. Thus, this implementation will set fixed values if INCREASE/DECREASE was received from KNX
	"""

	def __init__(self, mqtt_dimmer: str, knx_switch_ctr: str | None = None, knx_dimmer_ctr: str | None = None, increase_value: int = 60, decrease_value: int = 30) -> None:
		"""Create object of KNX to MQTT bridge

		:param mqtt_dimmer: name of MQTT item
		:param knx_switch_ctr: name of KNX switch-control item
		:param knx_dimmer_ctr: name of KNX dimmer-control item
		:param increase_value: value which is set when INCREASE was received.
		:param decrease_value: value which is set when DECREASE was received.
		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: If config is not valid
		"""
		if knx_switch_ctr is None and knx_dimmer_ctr is None:
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"At least one KNX item must be given! knx_switch_ctr = {knx_switch_ctr} | knx_dimmer_ctr = {knx_dimmer_ctr}")

		knx_name = knx_switch_ctr if knx_switch_ctr else knx_dimmer_ctr

		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, f"{knx_name}__{mqtt_dimmer}")

		self.__increase_value = increase_value
		self.__decrease_value = decrease_value

		self._mqtt_item = HABApp.openhab.items.DimmerItem.get_item(mqtt_dimmer)
		self._knx_dimmer_item = HABApp.openhab.items.DimmerItem.get_item(knx_dimmer_ctr) if knx_dimmer_ctr else None
		self._knx_switch_item = HABApp.openhab.items.SwitchItem.get_item(knx_switch_ctr) if knx_switch_ctr else None

		self._mqtt_item.listen_event(self._cb_mqtt_event, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._knx_dimmer_item is not None:
			self._knx_dimmer_item.listen_event(self._cb_knx_event, HABApp.openhab.events.ItemCommandEventFilter())
		if self._knx_switch_item is not None:
			self._knx_switch_item.listen_event(self._cb_knx_event, HABApp.openhab.events.ItemCommandEventFilter())
		self._instance_logger.debug("successful!")

	def _cb_knx_event(self, event: HABApp.openhab.events.ItemCommandEvent) -> None:
		"""Callback, which is called if a KNX command received.

		:param event: HABApp event
		"""
		if isinstance(event.value, (int, float)):
			self._mqtt_item.oh_send_command(event.value)
		elif event.value in {"ON", "OFF"}:
			self._mqtt_item.oh_send_command(event.value)
		elif event.value == "INCREASE":
			target_value = self.__increase_value if self._mqtt_item.value < self.__increase_value else 100
			self._mqtt_item.oh_send_command(target_value)
		elif event.value == "DECREASE":
			target_value = self.__decrease_value if self._mqtt_item.value > self.__decrease_value else 0
			self._mqtt_item.oh_send_command(target_value)
		else:
			self._instance_logger.error(f"command '{event.value}' ist not supported!")

	def _cb_mqtt_event(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is called if a MQTT state change event happens.

		:param event: HABApp event
		"""
		if self._knx_dimmer_item is not None:
			self._knx_dimmer_item.oh_post_update(event.value)

		if self._knx_switch_item is not None:
			self._knx_switch_item.oh_post_update("ON" if event.value > 0 else "OFF")
