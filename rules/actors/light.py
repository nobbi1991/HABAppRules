"""Rule manage a light."""
import logging

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.interface
import HABApp.openhab.items
import HABApp.util

import rules.common.helper
import rules.common.state_machine_rule

LOGGER = logging.getLogger("HABApp.actors.light")
LOGGER.setLevel("DEBUG")


# pylint: disable=no-member
class Light(rules.common.state_machine_rule.StateMachineRule):
	"""Rules class to manage sleep state."""

	states = [
		{"name": "manual"},
		{"name": "auto", "initial": "init", "children": [
			{"name": "init"},
			{"name": "on"},
			{"name": "preoff"},
			{"name": "off"},
			{"name": "leaving"},
			{"name": "presleep"},
		]}
	]

	trans = [
		{"trigger": "manual_on", "source": "auto", "dest": "manual"},
		{"trigger": "manual_off", "source": "manual", "dest": "auto"},
		{"trigger": "hand_on", "source": "auto_off", "dest": "auto_on"},
		{"trigger": "hand_off", "source": ["auto_on", "auto_leaving", "auto_presleep"], "dest": "auto_off"},
		{"trigger": "auto_on_timeout", "source": "auto_on", "dest": "auto_preoff"},
		{"trigger": "auto_preoff_timeout", "source": "auto_preoff", "dest": "auto_off"},
		{"trigger": "leaving_started", "source": ["auto_on", "auto_off"], "dest": "auto_leaving"},
		{"trigger": "leaving_timeout", "source": "auto_leaving", "dest": "auto_off"},
		{"trigger": "sleep_started", "source": ["auto_on", "auto_off"], "dest": "auto_presleep"},
		{"trigger": "presleep_timeout", "source": "auto_presleep", "dest": "auto_off"},
	]

	def __init__(self, name_light: str, presleep_timeout: int = 0, leaving_timeout: int = 0) -> None:
		"""Init of Sleep object.

		:param name_light: name of OpenHAB light item (SwitchItem | DimmerItem)
		"""
		super().__init__()

		# init items
		light_item = HABApp.core.Items.get_item(name_light)
		print(type(light_item))
		if isinstance(light_item, HABApp.openhab.items.dimmer_item.DimmerItem):
			self.__item_light = HABApp.openhab.items.DimmerItem.get_item(name_light)
		elif isinstance(light_item, HABApp.openhab.items.switch_item.SwitchItem):
			self.__item_light = HABApp.openhab.items.SwitchItem.get_item(name_light)
		else:
			raise Exception(f"type: {type(light_item)} is not supported!")

		# init state machine
		self.state_machine = rules.common.state_machine_rule.HierarchicalStateMachineWithTimeout(
			model=self,
			states=self.states,
			transitions=self.trans,
			initial=self._get_initial_state("manual"),
			ignore_invalid_triggers=True,
			after_state_change="_update_openhab_state")

		self.__item_light.listen_event(self.cb_temp_state_change, HABApp.openhab.events.ItemStateChangedEvent)
		self.__item_light.listen_event(self.cb_temp_state_change, HABApp.openhab.events.ItemCommandEvent)

	def is_on(self) -> bool:
		return True

	def cb_temp_state_change(self, event):
		print(f"StateChangeEvent: {event}")

	def cb_temp_command(self, event):
		print(f"CommandEvent: {event}")


class LightExtended(Light):

	def __init__(self, name_light):
		# add additional states
		auto_state: dict[str, list] = next(state for state in self.states if state["name"] == "auto")
		auto_state["children"].append({"name": "door"})
		auto_state["children"].append({"name": "movement"})
		auto_state["children"].append({"name": "preoff"})

		# add additional transitions
		self.trans.append({"trigger": "door_opened", "source": "auto_off", "dest": "auto_door"})
		self.trans.append({"trigger": "movement_detected", "source": "auto_door", "dest": "auto_movement"})
		self.trans.append({"trigger": "door_timeout", "source": "auto_door", "dest": "auto_off"})
		self.trans.append({"trigger": "movement_on", "source": "auto_off", "dest": "auto_movement"})
		self.trans.append({"trigger": "movement_off", "source": "auto_movement", "dest": "auto_preoff"})
		self.trans.append({"trigger": "preoff_timeout", "source": "auto_preoff", "dest": "auto_off"})
		self.trans.append({"trigger": "movement_on", "source": "auto_preoff", "dest": "auto_movement"})
		self.trans.append({"trigger": "door_closed", "source": "auto_leaving", "dest": "auto_off"})

		super().__init__(name_light)


# light = Light("I11_01_Sofa")

# 	LightExtended("bla")
