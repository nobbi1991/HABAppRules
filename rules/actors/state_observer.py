from __future__ import annotations

import logging
import typing

import HABApp
import HABApp.core.Items
import HABApp.openhab.interface
import HABApp.openhab.items

LOGGER = logging.getLogger("HABApp.actors.state_observer")
LOGGER.setLevel("DEBUG")


class StateObserver(HABApp.Rule):

	def __init__(
			self,
			item_name: str,
			callback_manual_detected: typing.Callable[[HABApp.openhab.events.base_event.OpenhabEvent, str], None],
			additional_command_names: list[str] = None,
			control_names: list[str] = None):
		super().__init__()

		self._wait_for_value = False
		self.__send_commands = []
		self.__cb_manual_detected = callback_manual_detected

		self.__item = HABApp.openhab.items.OpenhabItem.get_item(item_name)
		self.__expected_value_type = self.__init_expected_types()

		self.__command_items = [HABApp.openhab.items.OpenhabItem.get_item(name) for name in additional_command_names] if additional_command_names else []
		self.__control_items = [HABApp.openhab.items.OpenhabItem.get_item(name) for name in control_names] if control_names else []
		self.__check_item_types()

		self._value = self.__item.value

		self.__item.listen_event(self.__cb_value_change, HABApp.openhab.events.ItemStateEvent)
		HABApp.util.EventListenerGroup().add_listener(self.__command_items + [self.__item], self.__cb_command, HABApp.openhab.events.ItemCommandEvent).listen()
		HABApp.util.EventListenerGroup().add_listener(self.__control_items, self.__cb_control, HABApp.openhab.events.ItemCommandEvent).listen()

	@property
	def value(self):
		return self._value

	@property
	def wait_for_value(self):
		return self._wait_for_value

	def __init_expected_types(self):
		if (item_type := type(self.__item)) in [HABApp.openhab.items.DimmerItem, HABApp.openhab.items.RollershutterItem]:
			return int, float
		if item_type == HABApp.openhab.items.SwitchItem:
			return str  # todo maybe OnOffValue ?!
		raise Exception("Type not supported!")

	def __check_item_types(self):

		target_type = type(self.__item)

		wrong_types = []
		for item in self.__command_items + self.__control_items:
			if type(item) != target_type:
				wrong_types.append(f"{item.name} <{type(item).__name__}>")

		if wrong_types:
			LOGGER.error(msg := f"Found items with wrong item type. Expected: {target_type.__name__}. Wrong: {' | '.join(wrong_types)}")
			raise TypeError(msg)

	# def __check_temp(self):
	# 	# todo add checker if thing is configured correctly
	#
	# 	things = []
	# 	things_complete = []
	# 	start_time = time.time()
	# 	for thing in self.get_items(HABApp.openhab.items.Thing):
	# 		things.append(thing.name)
	# 		things_complete.append(HABApp.openhab.interface.get_thing(thing.name))
	#
	# 	end_time = time.time()
	# 	print(f"elapsed_time: {end_time - start_time}")
	#
	# # bla = [thing for thing in things_complete if "Dimm" in thing.name]
	# # print(bla)

	def send_command(self, value):
		self._value = value
		self.__send_commands.append(value)
		self.__item.oh_send_command(value)

	def __cb_value_change(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		if self._wait_for_value and isinstance(event.value, self.__expected_value_type):
			self._wait_for_value = False
		self.__update_value(event.value)

	def __cb_command(self, event: HABApp.openhab.events.ItemCommandEvent):
		if event.value in self.__send_commands:
			self.__send_commands.remove(event.value)
		else:
			self.__check_manual(event, "Manual from OpenHAB")

	def __cb_control(self, event: HABApp.openhab.events.ItemCommandEvent):
		self.__check_manual(event, "Manual from KNX-Bus")

	def __check_manual(self, event: HABApp.openhab.events.ItemCommandEvent, message: str):
		self.__cb_manual_detected(event, message)
		if event.value != self._value:
			self._wait_for_value = True

	def __update_value(self, value):
		self._value = value


# def temp_print_manual(event: HABApp.openhab.events.base_event.OpenhabEvent, message: str):
# 	print(f"{message}: {event}")
#
#
# observer = StateObserver("I11_01_Sofa", callback_manual_detected=temp_print_manual, control_names=["I11_01_Sofa_ctr"])
#
# import time
#
# # observer.send_command(3)
# # time.sleep(3)
# # print(observer.value)
#
# time.sleep(0.5)
# observer.send_command(20)
# time.sleep(0.5)
# observer.send_command(40)
# time.sleep(1)
# observer.send_command(60)
# time.sleep(1.5)
# observer.send_command(80)
# time.sleep(2)
# observer.send_command(90)
# time.sleep(3)
# observer.send_command(100)
#
# time.sleep(1)
# observer.send_command(0)


#

# time.sleep(3)
# print(f"{observer.value} | {observer._StateObserver__item.value}")

# todo: wenn licht hat min/max wert stimmt realer und send_command value nicht überein
# todo: should work for: switch / dimmer / rollershutter


# todo: try to get
