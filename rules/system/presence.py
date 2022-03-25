import os
import threading
import typing

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.interface
import HABApp.openhab.items
import transitions.extensions
import transitions.extensions.states

import rules.common.state_machine_rule

os.environ["PATH"] += r"C:\Program Files\Graphviz\bin"


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class StateMachineWithTimeout(transitions.Machine):
    pass


class Presence(rules.common.state_machine_rule.StateMachineRule):
    """Rules class to manage presence of a home."""

    states = [{"name": "presence"},
              {"name": "leaving", "timeout": 5 * 60, "on_timeout": "absence_detected"},  # leaving takes 5 minutes
              {"name": "absence", "timeout": 1.5 * 24 * 3600, "on_timeout": "long_absence_detected"},  # switch to long absence after 1.5 days
              {"name": "long_absence"}
              ]

    trans = [
        {'trigger': 'presence_detected', 'source': ['absence', 'long_absence'], 'dest': 'presence'},
        {'trigger': 'leaving_detected', 'source': 'presence', 'dest': 'leaving'},
        {'trigger': 'abort_leaving', 'source': 'leaving', 'dest': 'presence'},
        {'trigger': 'absence_detected', 'source': ['presence', 'leaving'], 'dest': 'absence'},
        {'trigger': 'long_absence_detected', 'source': 'absence', 'dest': 'long_absence'},
    ]

    def __init__(self, name_presence: str, outside_door_names: typing.List[str], leaving_name: str, phone_names: typing.List[str] = None) -> None:
        """Init of Presence object.

        :param name_presence: name of OpenHAB presence item
        :param outside_door_names: list of names of OpenHAB outdoor door items
        :param leaving_name: name of OpenHAB leaving item
        """
        super().__init__()

        self.state_machine = StateMachineWithTimeout(model=self,
                                                     states=self.states,
                                                     transitions=self.trans,
                                                     initial=self._get_initial_state("presence"),
                                                     ignore_invalid_triggers=True,
                                                     after_state_change="_update_openhab_state")

        for name in outside_door_names:
            door_item = HABApp.openhab.items.ContactItem.get_item(name)
            door_item.listen_event(self._cb_outside_door, HABApp.openhab.events.ItemStateChangedEvent)

        self.__leaving_item = HABApp.openhab.items.SwitchItem.get_item(leaving_name)
        self.__leaving_item.listen_event(self._cb_leaving, HABApp.openhab.events.ItemStateChangedEvent)

        self.__presence_item = HABApp.openhab.items.SwitchItem.get_item(name_presence)
        self.__presence_item.listen_event(self._cb_presence, HABApp.openhab.events.ItemStateChangedEvent)

        self.__phone_items = []
        self.__phone_absence_timer: threading.Timer = None
        if phone_names:
            for name in phone_names:
                self.__phone_items.append(HABApp.openhab.items.SwitchItem.get_item(name))
                self.__phone_items[-1].listen_event(self._cb_phone, HABApp.openhab.events.ItemStateChangedEvent)

    def _update_openhab_state(self) -> None:
        """Extend _update_openhab state of base class to also update other openhab items."""
        super()._update_openhab_state()

        # update presence item
        target_value = "ON" if self.state in ["presence", "leaving"] else "OFF"
        self._send_if_different(self.__presence_item.name, target_value)

        # update leaving item
        if self.state != "leaving":
            self._send_if_different(self.__leaving_item.name, "OFF")

    def _cb_outside_door(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if any outside door changed state.

        :param event: state change event of door item
        """
        if event.value == "OPEN" and self.state != "presence":
            self.presence_detected()

    def _cb_leaving(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if leaving item changed state.

        :param event: Item state change event of leaving item
        """
        if event.value == "ON" and self.state == "presence":
            self.leaving_detected()
        if event.value == "OFF" and self.state == "leaving":
            self.abort_leaving()

    def _cb_presence(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if presence item changed state.

        :param event: Item state change event of presence item
        """
        if event.value == "ON" and self.state in ["absence", "long_absence"]:
            self.presence_detected()
        elif event.value == "OFF" and self.state in ["presence", "leaving"]:
            self.absence_detected()

    def _cb_phone(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback, which is called if a phone state changed.

        :param event: Item state change event of phone item
        """
        active_phones = len([phone for phone in self.__phone_items if phone.value == "ON"])
        if active_phones == 1 and event.value == "ON":
            # first phone switched to ON
            if self.__phone_absence_timer:
                self.__phone_absence_timer.cancel()
                self.__phone_absence_timer = None

            if self.state in ["absence", "long_absence"]:
                self.presence_detected()
            elif self.state in ["leaving"]:
                self.abort_leaving()

        elif active_phones == 0 and event.value == "OFF":
            # last phone switched to OFF
            self.__phone_absence_timer = threading.Timer(30 * 60, self.__set_leaving_through_phone)
            self.__phone_absence_timer.start()

    def __set_leaving_through_phone(self):
        if self.state == "presence":
            self.leaving_detected()
        self.__phone_absence_timer = None
