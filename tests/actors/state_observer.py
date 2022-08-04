"""Test Presence rule."""
import collections
import time
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.state_observer
import habapp_rules.common.state_machine_rule
import tests.common.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.timer


# pylint: disable=protected-access
class TestStateObserverSwitch(unittest.TestCase):
	"""Tests cases for testing StateObserver for switch item."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.send_command_mock_patcher.stop)
		self.send_command_mock = self.send_command_mock_patcher.start()

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch", 0)

		self._cb_on = unittest.mock.MagicMock()
		self._cb_off = unittest.mock.MagicMock()
		self._observer_switch = habapp_rules.actors.state_observer.StateObserverSwitch("Unittest_Switch", cb_on=self._cb_on, cb_off=self._cb_off)

	def test_command_from_habapp(self):
		"""Test HABApp rule triggers a command -> no manual should be detected."""
		self._observer_switch.send_command("OFF")
		tests.helper.oh_item.item_command_event("Unittest_Switch", "OFF")
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()

		self._observer_switch.send_command("OFF")
		tests.helper.oh_item.item_command_event("Unittest_Switch", "OFF")
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()

		self._observer_switch.send_command("ON")
		tests.helper.oh_item.item_command_event("Unittest_Switch", "ON")
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()

		self._observer_switch.send_command("ON")
		tests.helper.oh_item.item_command_event("Unittest_Switch", "ON")
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()

		self._observer_switch.send_command("OFF")
		tests.helper.oh_item.item_command_event("Unittest_Switch", "OFF")
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()

		self.assertEqual([], self._observer_switch._send_commands)

	def test_manu_from_openhab(self):
		"""Test manual detection from openHAB."""
		TestCase = collections.namedtuple("TestCase", "command, num_cb_on, num_cb_off")

		test_cases = [
			TestCase("ON", 1, 0),
			TestCase("ON", 1, 0),
			TestCase("OFF", 1, 1),
			TestCase("OFF", 1, 1),
			TestCase("ON", 2, 1),
		]

		for test_case in test_cases:
			tests.helper.oh_item.item_state_event("Unittest_Switch", test_case.command)
			self.assertEqual(test_case.num_cb_on, self._cb_on.call_count)
			self.assertEqual(test_case.num_cb_off, self._cb_off.call_count)
			self._cb_on.assert_called_with(unittest.mock.ANY, "Manual from extern")

	def test_manu_from_extern(self):
		"""Test manual detection from extern."""
		TestCase = collections.namedtuple("TestCase", "command, num_cb_on, num_cb_off")

		test_cases = [
			TestCase("ON", 1, 0),
			TestCase("ON", 1, 0),
			TestCase("OFF", 1, 1),
			TestCase("OFF", 1, 1),
			TestCase("ON", 2, 1),
		]

		for test_case in test_cases:
			tests.helper.oh_item.item_command_event("Unittest_Switch", test_case.command)
			self.assertEqual(test_case.num_cb_on, self._cb_on.call_count)
			self.assertEqual(test_case.num_cb_off, self._cb_off.call_count)
			self._cb_on.assert_called_with(unittest.mock.ANY, "Manual from OpenHAB")
			tests.helper.oh_item.item_state_event("Unittest_Switch", test_case.command)
			self.assertEqual(test_case.command, self._observer_switch.value)

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()


# pylint: disable=protected-access
class TestStateObserverDimmer(unittest.TestCase):
	"""Tests cases for testing StateObserver for dimmer item."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.send_command_mock_patcher.stop)
		self.send_command_mock = self.send_command_mock_patcher.start()

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_ctr", "OFF")

		self._cb_on = unittest.mock.MagicMock()
		self._cb_off = unittest.mock.MagicMock()
		self._observer_dimmer = habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Dimmer", cb_on=self._cb_on, cb_off=self._cb_off, control_names=["Unittest_Dimmer_ctr"])

	def test__check_item_types(self):
		"""Test if wrong item types are detected correctly."""
		with self.assertRaises(TypeError) as context:
			habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Dimmer", cb_on=self._cb_on, cb_off=self._cb_off, control_names=["Unittest_Dimmer_ctr", "Unittest_Switch_ctr"])
		self.assertEqual("Found items with wrong item type. Expected: DimmerItem. Wrong: Unittest_Switch_ctr <SwitchItem>", str(context.exception))

	def test_check_different_value(self):
		"""Test _check_different_value."""
		TestCase = collections.namedtuple("TestCase", "last_value, new_value, result")

		test_cases = [
			TestCase(0, 0, False),
			TestCase(0, 20, True),
			TestCase(0, "ON", True),
			TestCase(0, "OFF", False),
			TestCase(0, "INCREASE", True),
			TestCase(0, "DECREASE", True),

			TestCase(60, 0, True),
			TestCase(60, 40, False),
			TestCase(60, 80, False),
			TestCase(60, "ON", False),
			TestCase(60, "OFF", True),
			TestCase(60, "INCREASE", True),
			TestCase(60, "DECREASE", True),

			TestCase("OFF", 0, False),
			TestCase("OFF", 20, True),
			TestCase("OFF", "ON", True),
			TestCase("OFF", "OFF", False),
			TestCase("OFF", "INCREASE", True),
			TestCase("OFF", "DECREASE", True),

			TestCase("ON", 0, True),
			TestCase("ON", 40, False),
			TestCase("ON", 80, False),
			TestCase("ON", "ON", False),
			TestCase("ON", "OFF", True),
			TestCase("ON", "INCREASE", True),
			TestCase("ON", "DECREASE", True),

			TestCase(None, 0, True),
			TestCase(None, 40, True),
			TestCase(None, 80, True),
			TestCase(None, "ON", True),
			TestCase(None, "OFF", True),
			TestCase(None, "INCREASE", True),
			TestCase(None, "DECREASE", True),
		]

		for test_case in test_cases:
			self._observer_dimmer._StateObserverDimmer__last_received_value = test_case.last_value
			self.assertEqual(test_case.result, self._observer_dimmer._StateObserverDimmer__check_different_value(test_case.new_value), test_case)

	def test_command_from_habapp(self):
		"""Test HABApp rule triggers a command -> no manual should be detected."""
		self._observer_dimmer.send_command(0)
		tests.helper.oh_item.item_command_event("Unittest_Dimmer", 0)
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()
		self._observer_dimmer.send_command(30)
		tests.helper.oh_item.item_command_event("Unittest_Dimmer", 30)
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()
		self._observer_dimmer.send_command(100)
		tests.helper.oh_item.item_command_event("Unittest_Dimmer", 100)
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()
		self._observer_dimmer.send_command(0)
		tests.helper.oh_item.item_command_event("Unittest_Dimmer", 0)
		self._cb_on.assert_not_called()
		self._cb_off.assert_not_called()

		self.assertEqual([], self._observer_dimmer._send_commands)

	def test_manu_from_ctr(self):
		"""Test manual detection from control item."""
		TestCase = collections.namedtuple("TestCase", "command, state, num_cb_on, num_cb_off")

		test_cases = [
			TestCase("ON", 100, 1, 0),
			TestCase(100, 100, 1, 0),
			TestCase(100, 100, 1, 0),
			TestCase(0, 0, 1, 1),
			TestCase("ON", 100, 2, 1),
			TestCase("OFF", 0, 2, 2),
			TestCase("INCREASE", 30, 3, 2)
		]

		for test_case in test_cases:
			tests.helper.oh_item.item_state_event("Unittest_Dimmer", test_case.command)
			self.assertEqual(test_case.num_cb_on, self._cb_on.call_count)
			self.assertEqual(test_case.num_cb_off, self._cb_off.call_count)
			self._cb_on.assert_called_with(unittest.mock.ANY, "Manual from extern")
			tests.helper.oh_item.item_state_event("Unittest_Dimmer", test_case.state)
			self.assertEqual(test_case.state, self._observer_dimmer.value)

	def test_basic_behavior_on_knx(self):
		"""Test basic behavior. Switch ON via KNX"""
		# === Switch ON via KNX button ===
		# set initial state
		self._cb_on.reset_mock()
		self._observer_dimmer._value = 0
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0
		# send commands
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", "ON")
		self._cb_on.assert_called_once_with(unittest.mock.ANY, "Manual from extern")
		self.assertEqual(0, self._observer_dimmer.value)
		# In real system, this command is triggered about 2 sec later
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", 100)
		self.assertEqual(100, self._observer_dimmer.value)
		self._cb_on.assert_called_once_with(unittest.mock.ANY, "Manual from extern")

		# === Switch ON via KNX value ===
		# set initial state
		self._cb_on.reset_mock()
		self._observer_dimmer._value = 0
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0
		# send commands
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", 42)
		self._cb_on.assert_called_once_with(unittest.mock.ANY, "Manual from extern")
		self.assertEqual(42, self._observer_dimmer.value)
		# In real system, this command is triggered about 2 sec later
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", 42)
		self.assertEqual(42, self._observer_dimmer.value)
		self._cb_on.assert_called_once_with(unittest.mock.ANY, "Manual from extern")

		# === Switch ON via KNX from group ===
		# set initial state
		self._cb_on.reset_mock()
		self._observer_dimmer._value = 0
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0
		# send commands
		tests.helper.oh_item.item_command_event("Unittest_Dimmer_ctr", "ON")
		self._cb_on.assert_called_once_with(unittest.mock.ANY, "Manual from extern")
		self.assertEqual(0, self._observer_dimmer.value)
		# In real system, this command is triggered about 2 sec later
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", 80)
		self.assertEqual(80, self._observer_dimmer.value)
		self._cb_on.assert_called_once_with(unittest.mock.ANY, "Manual from extern")

		# === Value via KNX from group ===
		# set initial state
		self._cb_on.reset_mock()
		self._observer_dimmer._value = 0
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0
		# send commands
		tests.helper.oh_item.item_command_event("Unittest_Dimmer_ctr", 42)
		self._cb_on.assert_called_once_with(unittest.mock.ANY, "Manual from extern")
		self.assertEqual(0, self._observer_dimmer.value)
		# In real system, this command is triggered about 2 sec later
		tests.helper.oh_item.item_state_event("Unittest_Dimmer", 60)
		self.assertEqual(60, self._observer_dimmer.value)
		self._cb_on.assert_called_once_with(unittest.mock.ANY, "Manual from extern")

	def test_manu_from_openhab(self):
		"""Test manual detection from control item."""
		TestCase = collections.namedtuple("TestCase", "command, state, num_cb_on, num_cb_off")

		test_cases = [
			TestCase(100, 100, 1, 0),
			TestCase(100, 100, 1, 0),
			TestCase(0, 0, 1, 1),
			TestCase("ON", 100, 2, 1),
			TestCase("OFF", 0, 2, 2),
			TestCase("INCREASE", 30, 3, 2)
		]

		for test_case in test_cases:
			tests.helper.oh_item.item_command_event("Unittest_Dimmer", test_case.command)
			self.assertEqual(test_case.num_cb_on, self._cb_on.call_count)
			self.assertEqual(test_case.num_cb_off, self._cb_off.call_count)
			self._cb_on.assert_called_with(unittest.mock.ANY, "Manual from OpenHAB")
			tests.helper.oh_item.item_state_event("Unittest_Dimmer", test_case.state)
			self.assertEqual(test_case.state, self._observer_dimmer.value)

	def test_switch_off_via_decrease(self):
		"""Test if switch-off-callback is called when light is switched off via decrease command."""
		# test if thread was started correctly
		wait_thread_mock = unittest.mock.MagicMock()
		with unittest.mock.patch("threading.Thread", return_value=wait_thread_mock) as threading_mock:
			threading_mock.assert_not_called()
			wait_thread_mock.start.assert_not_called()
			self.assertFalse(self._observer_dimmer._StateObserverDimmer__wait_after_decrease_active)

			tests.helper.oh_item.item_command_event("Unittest_Dimmer", "DECREASE")

			threading_mock.assert_called_with(target=unittest.mock.ANY, args=(15, unittest.mock.ANY, "Manual from OpenHAB"))
			wait_thread_mock.start.assert_called_once()
			self.assertTrue(self._observer_dimmer._StateObserverDimmer__wait_after_decrease_active)

		# test thread
		with unittest.mock.patch("time.sleep", spec=time.sleep):
			# exit if __wait_after_decrease is not set
			self._observer_dimmer._StateObserverDimmer__wait_after_decrease_active = False
			self._observer_dimmer._StateObserverDimmer__check_decrease_switched_off(10, None, "some message")
			self._cb_off.assert_not_called()

			# test no callback if target value is not zero
			with unittest.mock.patch("habapp_rules.actors.state_observer.StateObserverDimmer.value", new_callable=unittest.mock.PropertyMock) as value_mock:
				value_mock.side_effect = [100, 100, 100, 10]
				self._observer_dimmer._StateObserverDimmer__wait_after_decrease_active = True
				self._observer_dimmer._StateObserverDimmer__check_decrease_switched_off(10, None, "some message")
				self._cb_off.assert_not_called()

			# test no callback if target value is zero
			with unittest.mock.patch("habapp_rules.actors.state_observer.StateObserverDimmer.value", new_callable=unittest.mock.PropertyMock) as value_mock:
				value_mock.side_effect = [100, 100, 100, 0]
				self._observer_dimmer._StateObserverDimmer__wait_after_decrease_active = True
				self._observer_dimmer._StateObserverDimmer__check_decrease_switched_off(10, None, "some message")
				self._cb_off.assert_called_once()

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
