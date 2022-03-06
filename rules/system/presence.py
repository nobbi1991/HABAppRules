import os
import typing

import HABApp.openhab.definitions
import HABApp.openhab.events
import HABApp.openhab.interface
import HABApp.openhab.items
import transitions.extensions
import transitions.extensions.states

os.environ["PATH"] += r"C:\Program Files\Graphviz\bin"


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class StateMachineWithTimeout(transitions.Machine):
    pass


class Presence(HABApp.Rule):
    states = [{"name": "presence"},
              {"name": "leaving", "timeout": 5 * 60, "on_timeout": "absence_detected"},
              {"name": "absence", "timeout": 1.5 * 24 * 3600, "on_timeout": "detected_long_absence"},
              {"name": "long_absence"}
              ]

    trans = [
        {'trigger': 'presence_detected', 'source': ['absence', 'long_absence'], 'dest': 'presence'},
        {'trigger': 'leaving_detected', 'source': 'presence', 'dest': 'leaving'},
        {'trigger': 'abort_leaving', 'source': 'leaving', 'dest': 'presence'},
        {'trigger': 'absence_detected', 'source': ['presence', 'leaving'], 'dest': 'absence'},
        {'trigger': 'long_absence_detected', 'source': 'absence', 'dest': 'long_absence'},
    ]

    def __init__(self, name_presence: str, outside_door_names: typing.List[str], leaving_name: str) -> None:
        super().__init__()

        self.state_machine = StateMachineWithTimeout(model=self,
                                                     states=self.states,
                                                     transitions=self.trans,
                                                     initial=self._get_initial_state(),
                                                     ignore_invalid_triggers=True,
                                                     after_state_change="_update_openhab_state")

        for name in outside_door_names:
            door_item = HABApp.openhab.items.ContactItem.get_item(name)
            door_item.listen_event(self._cb_outside_door, HABApp.openhab.events.ItemStateChangedEvent)

        leaving_item = HABApp.openhab.items.SwitchItem.get_item(leaving_name)
        leaving_item.listen_event(self._cb_leaving, HABApp.openhab.events.ItemStateEvent)

    def _get_initial_state(self):
        return "presence"

    def _update_openhab_state(self):
        pass

    def _cb_outside_door(self, event: HABApp.openhab.events.ItemStateChangedEvent):
        if event.value == "OPEN" and self.state != "presence":
            self.presence_detected()

    def _cb_leaving(self, event: HABApp.openhab.events.ItemStateEvent):
        if event.value == "ON" and self.state == "presence":
            self.leaving_detected()
