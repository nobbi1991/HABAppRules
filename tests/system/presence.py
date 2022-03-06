import pathlib
import unittest
import unittest.mock

import HABApp.rule.rule
import transitions.extensions
import transitions.extensions.states

import rules.system.presence


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class GraphMachineTimer(transitions.extensions.GraphMachine):
    pass


class TestPowerSwitch(unittest.TestCase):

    def setUp(self) -> None:
        self.mock_items = [
            (HABApp.openhab.items.ContactItem, "Unittest_Main_Door", "CLOSED"),
            (HABApp.openhab.items.ContactItem, "Unittest_Side_Door", "CLOSED"),
            (HABApp.openhab.items.SwitchItem, 'Unittest_Leaving', 'OFF'),
            (HABApp.openhab.items.SwitchItem, 'Unittest_Switch', 'OFF'),
            (HABApp.openhab.items.SwitchItem, 'Unittest_Sleep', 'OFF'),
            (HABApp.openhab.items.SwitchItem, 'Unittest_Presence', 'OFF'),
            (HABApp.openhab.items.StringItem, 'RUnittest_Switch_state', ''),
            (HABApp.openhab.items.SwitchItem, 'RUnittest_Switch_manual', 'OFF')
        ]

        for item_type, name, value in self.mock_items:
            if name in HABApp.core.Items._ALL_ITEMS:
                HABApp.core.Items.pop_item(name)
            item = item_type(name, value)
            HABApp.core.Items.add_item(item)

        with unittest.mock.patch.object(HABApp.rule.rule.Rule, "__init__", autospec=True) as rule_init_mock, \
                unittest.mock.patch("HABApp.openhab.interface.item_exists", autospec=True) as item_exist_mock, \
                unittest.mock.patch("HABApp.core.items.base_item.BaseItem.listen_event", autospec=True, return_value=None) as listen_event_mock:
            item_exist_mock.return_value = True
            rule_init_mock.return_value = None
            listen_event_mock.return_value = None
            self._presence = rules.system.presence.Presence("I00_00_Presence", outside_door_names=["Unittest_Main_Door", "Unittest_Side_Door"], leaving_name="Unittest_Leaving")

    def test_create_graph(self):
        self._presence_graph = GraphMachineTimer(model=self._presence,
                                                 states=self._presence.states,
                                                 transitions=self._presence.trans,
                                                 initial=self._presence.state)

        self._presence_graph.get_graph().draw(pathlib.Path(__file__).parent / "Presence.png", format="png", prog="dot")

    def test_cb_outside_door(self):
        self._presence.state_machine.set_state("absence")
        self.assertEqual(self._presence.state, "absence")

        self._presence._cb_outside_door(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Main_Door", "CLOSED", "CLOSED"))
        self.assertEqual(self._presence.state, "absence")

        self._presence._cb_outside_door(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Main_Door", "OPEN", "CLOSED"))
        self.assertEqual(self._presence.state, "presence")

        self._presence._cb_outside_door(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Main_Door", "OPEN", "CLOSED"))
        self.assertEqual(self._presence.state, "presence")

        self._presence._cb_outside_door(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Main_Door", "CLOSED", "CLOSED"))
        self.assertEqual(self._presence.state, "presence")

    def test_cb_leaving(self):
        self._presence.state_machine.set_state("presence")
        self.assertEqual(self._presence.state, "presence")

        self._presence._cb_leaving(HABApp.openhab.events.ItemStateEvent("Unittest_Leaving", "OFF"))
        self.assertEqual(self._presence.state, "presence")

        self._presence._cb_leaving(HABApp.openhab.events.ItemStateEvent("Unittest_Leaving", "ON"))
        self.assertEqual(self._presence.state, "leaving")

    def tearDown(self) -> None:
        for _, name, _ in self.mock_items:
            HABApp.core.Items.pop_item(name)


if __name__ == "__main__":
    unittest.main()
