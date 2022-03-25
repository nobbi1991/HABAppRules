import pathlib
import threading
import unittest
import unittest.mock

import HABApp.rule.rule
import transitions.extensions
import transitions.extensions.states

import rules.common.state_machine_rule
import rules.system.presence
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.transitions


@transitions.extensions.states.add_state_features(transitions.extensions.states.Timeout)
class GraphMachineTimer(transitions.extensions.GraphMachine):
    pass


class TestPowerSwitch(unittest.TestCase):

    def setUp(self) -> None:
        """Setup testcase."""
        self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
        self.addCleanup(self.transitions_timer_mock_patcher.stop)
        self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

        self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
        self.addCleanup(self.threading_timer_mock_patcher.stop)
        self.threading_timer_mock = self.threading_timer_mock_patcher.start()

        self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.connection_handler.func_sync.send_command", new=tests.helper.oh_item.set_state)
        self.addCleanup(self.send_command_mock_patcher.stop)
        self.send_command_mock = self.send_command_mock_patcher.start()

        self.mock_items = [
            (HABApp.openhab.items.ContactItem, "Unittest_Main_Door", "CLOSED"),
            (HABApp.openhab.items.ContactItem, "Unittest_Side_Door", "CLOSED"),
            (HABApp.openhab.items.SwitchItem, 'Unittest_Leaving', 'OFF'),
            (HABApp.openhab.items.SwitchItem, 'Unittest_Phone1', 'OFF'),
            (HABApp.openhab.items.SwitchItem, 'Unittest_Phone2', 'OFF'),
            (HABApp.openhab.items.StringItem, "rules_system_presence_Presence", ""),
            (HABApp.openhab.items.SwitchItem, "Unittest_Presence", "")
        ]

        for item_type, name, value in self.mock_items:
            if name in HABApp.core.Items._ALL_ITEMS:
                HABApp.core.Items.pop_item(name)
            item = item_type(name, value)
            HABApp.core.Items.add_item(item)

        self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
        self.__runner.set_up()
        with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("Presence", "")):
            self._presence = rules.system.presence.Presence("Unittest_Presence", outside_door_names=["Unittest_Main_Door", "Unittest_Side_Door"], leaving_name="Unittest_Leaving", phone_names=["Unittest_Phone1", "Unittest_Phone2"])

    def test_create_graph(self):
        """Create state machine graph for documentation."""
        self._presence_graph = GraphMachineTimer(model=self._presence,
                                                 states=self._presence.states,
                                                 transitions=self._presence.trans,
                                                 initial=self._presence.state)

        self._presence_graph.get_graph().draw(pathlib.Path(__file__).parent / "Presence.png", format="png", prog="dot")

    def test_presence_trough_doors(self):
        """Test if outside doors set presence correctly."""
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF")
        self._presence.state_machine.set_state("absence")
        self.assertEqual(self._presence.state, "absence")

        self.__runner.process_events()
        tests.helper.oh_item.send_command("Unittest_Main_Door", "CLOSED", "CLOSED")
        self.assertEqual(self._presence.state, "absence")

        tests.helper.oh_item.send_command("Unittest_Main_Door", "OPEN", "CLOSED")
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.assert_state("Unittest_Presence", "ON")

        tests.helper.oh_item.send_command("Unittest_Main_Door", "OPEN", "CLOSED")
        self.assertEqual(self._presence.state, "presence")

        tests.helper.oh_item.send_command("Unittest_Main_Door", "CLOSED", "CLOSED")
        self.assertEqual(self._presence.state, "presence")

    def test_normal_leaving(self):
        """Test if 'normal' leaving works correctly."""
        self._presence.state_machine.set_state("presence")
        self.assertEqual(self._presence.state, "presence")

        tests.helper.oh_item.send_command("Unittest_Leaving", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")

        tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "leaving")
        self.transitions_timer_mock.assert_called_with(300, unittest.mock.ANY, args=unittest.mock.ANY)

        # call timeout and check if absence is active
        tests.helper.transitions.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "absence")

    def test_abort_leaving(self):
        """Test aborting of leaving state."""
        self._presence.state_machine.set_state("presence")
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.set_state("Unittest_Leaving", "ON")

        tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
        self.assertEqual(self._presence.state, "leaving")
        tests.helper.oh_item.assert_state("Unittest_Leaving", "ON")

        tests.helper.oh_item.send_command("Unittest_Leaving", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.assert_state("Unittest_Leaving", "OFF")

    def test_long_absence(self):
        """Test entering long_absence and leaving it."""
        # set initial state
        self._presence.state_machine.set_state("presence")
        tests.helper.oh_item.set_state("Unittest_Presence", "ON")

        # go to absence
        self._presence.absence_detected()
        self.assertEqual(self._presence.state, "absence")
        tests.helper.oh_item.assert_state("Unittest_Presence", "OFF")

        # check if timeout started, and stop the mocked timer
        self.transitions_timer_mock.assert_called_with(1.5 * 24 * 3600, unittest.mock.ANY, args=unittest.mock.ANY)
        tests.helper.transitions.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "long_absence")
        tests.helper.oh_item.assert_state("Unittest_Presence", "OFF")

        # check if presence is set after door open
        self._presence._cb_outside_door(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Main_Door", "OPEN", "CLOSED"))
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.assert_state("Unittest_Presence", "ON")

    def test_manual_change(self):
        """Test if change of presence object ist setting correct state."""
        # send manual off from presence
        self._presence.state_machine.set_state("presence")
        tests.helper.oh_item.send_command("Unittest_Presence", "ON", "OFF")
        self._presence._cb_presence(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Presence", "OFF", "ON"))
        self.assertEqual(self._presence.state, "absence")
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF", "ON")

        # send manual off from leaving
        self._presence.state_machine.set_state("leaving")
        tests.helper.oh_item.send_command("Unittest_Presence", "ON", "OFF")
        self._presence._cb_presence(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Presence", "OFF", "ON"))
        self.assertEqual(self._presence.state, "absence")
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF", "ON")

        # send manual on from absence
        self._presence.state_machine.set_state("absence")
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF", "ON")
        self._presence._cb_presence(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Presence", "ON", "OFF"))
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.send_command("Unittest_Presence", "ON", "OFF")

        # send manual on from long_absence
        self._presence.state_machine.set_state("long_absence")
        tests.helper.oh_item.send_command("Unittest_Presence", "OFF", "ON")
        self._presence._cb_presence(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Presence", "ON", "OFF"))
        self.assertEqual(self._presence.state, "presence")
        tests.helper.oh_item.send_command("Unittest_Presence", "ON", "OFF")

    def test_phones(self):
        """Test if presence is set correctly through phones."""
        # first phone switches to ON -> presence expected
        self._presence.state_machine.set_state("absence")
        tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")
        self.threading_timer_mock.assert_not_called()

        # second phone switches to ON -> no change expected
        tests.helper.oh_item.send_command("Unittest_Phone2", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")
        self.threading_timer_mock.assert_not_called()

        # second phone switches to OFF -> no change expected
        tests.helper.oh_item.send_command("Unittest_Phone2", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")
        self.threading_timer_mock.assert_not_called()

        # first phone switches to OFF -> timer should be started
        tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")
        self.threading_timer_mock.assert_called_once_with(1800, self._presence._Presence__set_leaving_through_phone)
        tests.helper.transitions.call_timeout(self.threading_timer_mock)
        self.assertEqual(self._presence.state, "leaving")

        # phone appears during leaving -> presence expected
        tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
        self.assertEqual(self._presence.state, "presence")
        self.assertIsNone(self._presence._Presence__phone_absence_timer)

        # phone leaves again -> leaving + absence expected
        tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
        self.assertEqual(self._presence.state, "presence")
        self.assertEqual(self.threading_timer_mock.call_count, 2)
        self.threading_timer_mock.assert_called_with(1800, self._presence._Presence__set_leaving_through_phone)
        tests.helper.transitions.call_timeout(self.threading_timer_mock)
        self.assertEqual(self._presence.state, "leaving")
        tests.helper.transitions.call_timeout(self.transitions_timer_mock)
        self.assertEqual(self._presence.state, "absence")

    def tearDown(self) -> None:
        """Tear down test case."""
        for _, name, _ in self.mock_items:
            HABApp.core.Items.pop_item(name)
        self.__runner.tear_down()


if __name__ == "__main__":
    unittest.main()
