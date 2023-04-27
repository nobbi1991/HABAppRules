"""Test Presence rule."""
import collections
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.state_observer
import habapp_rules.core.state_machine_rule
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

		for value in ["OFF", "OFF", "ON", "ON", "OFF"]:
			self._observer_switch.send_command(value)
			tests.helper.oh_item.item_command_event("Unittest_Switch", value)
			tests.helper.oh_item.item_state_change_event("Unittest_Switch", value)
			self._cb_on.assert_not_called()
			self._cb_off.assert_not_called()

	def test_manu_from_openhab(self):
		"""Test manual detection from openHAB."""
		TestCase = collections.namedtuple("TestCase", "command, cb_on_called, cb_off_called")

		test_cases = [
			TestCase("ON", True, False),
			TestCase("ON", False, False),
			TestCase("OFF", False, True),
			TestCase("OFF", False, False),
			TestCase("ON", True, False),
		]

		for test_case in test_cases:
			self._cb_on.reset_mock()
			self._cb_off.reset_mock()

			tests.helper.oh_item.item_state_change_event("Unittest_Switch", test_case.command)

			self.assertEqual(test_case.cb_on_called, self._cb_on.called)
			self.assertEqual(test_case.cb_off_called, self._cb_off.called)

			if test_case.cb_on_called:
				self._cb_on.assert_called_with(unittest.mock.ANY)
			if test_case.cb_off_called:
				self._cb_off.assert_called_with(unittest.mock.ANY)

	def test_manu_from_extern(self):
		"""Test manual detection from extern."""
		TestCase = collections.namedtuple("TestCase", "command, cb_on_called, cb_off_called")

		test_cases = [
			TestCase("ON", True, False),
			TestCase("ON", False, False),
			TestCase("OFF", False, True),
			TestCase("OFF", False, False),
			TestCase("ON", True, False),
		]

		for test_case in test_cases:
			self._cb_on.reset_mock()
			self._cb_off.reset_mock()

			tests.helper.oh_item.item_state_change_event("Unittest_Switch", test_case.command)

			self.assertEqual(test_case.cb_on_called, self._cb_on.called)
			self.assertEqual(test_case.cb_off_called, self._cb_off.called)
			if test_case.cb_on_called:
				self._cb_on.assert_called_with(unittest.mock.ANY)
			if test_case.cb_off_called:
				self._cb_off.assert_called_with(unittest.mock.ANY)
			tests.helper.oh_item.item_state_change_event("Unittest_Switch", test_case.command)
			self.assertEqual(test_case.command == "ON", self._observer_switch.value)

	def test_send_command_exception(self):
		"""Test if correct exceptions is raised."""
		with self.assertRaises(ValueError):
			self._observer_switch.send_command(2)

	def test_check_manual_exception(self):
		"""Test if correct exception is raised."""
		with self.assertRaises(ValueError):
			self._observer_switch._check_manual(HABApp.openhab.events.ItemCommandEvent("Item_name", "not_supported"))

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()


# pylint: disable=protected-access, no-member
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
		self._cb_changed = unittest.mock.MagicMock()
		self._observer_dimmer = habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Dimmer", cb_on=self._cb_on, cb_off=self._cb_off, cb_brightness_change=self._cb_changed, control_names=["Unittest_Dimmer_ctr"])

	def test_init(self):
		"""Test init of StateObserverDimmer."""
		self.assertEqual([], self._observer_dimmer._StateObserverBase__group_items)
		self.assertEqual(1, len(self._observer_dimmer._StateObserverBase__control_items))
		self.assertEqual("Unittest_Dimmer_ctr", self._observer_dimmer._StateObserverBase__control_items[0].name)

		observer_dimmer = habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Dimmer", cb_on=self._cb_on, cb_off=self._cb_off, cb_brightness_change=self._cb_changed, group_names=["Unittest_Dimmer_ctr"])
		self.assertEqual(1, len(observer_dimmer._StateObserverBase__group_items))
		self.assertEqual("Unittest_Dimmer_ctr", observer_dimmer._StateObserverBase__group_items[0].name)
		self.assertEqual([], observer_dimmer._StateObserverBase__control_items)

	def test__check_item_types(self):
		"""Test if wrong item types are detected correctly."""
		with self.assertRaises(TypeError) as context:
			habapp_rules.actors.state_observer.StateObserverDimmer("Unittest_Dimmer", cb_on=self._cb_on, cb_off=self._cb_off, control_names=["Unittest_Dimmer_ctr", "Unittest_Switch_ctr"])
		self.assertEqual("Found items with wrong item type. Expected: DimmerItem. Wrong: Unittest_Switch_ctr <SwitchItem>", str(context.exception))

	def test_command_from_habapp(self):
		"""Test HABApp rule triggers a command -> no manual should be detected."""
		for value in [100, 0, 30, 100, 0, "ON", "OFF", 0, 80]:
			self._observer_dimmer.send_command(value)
			tests.helper.oh_item.item_command_event("Unittest_Dimmer", value)
			tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", value)
			self._cb_on.assert_not_called()
			self._cb_off.assert_not_called()
			self._cb_changed.assert_not_called()

	def test_manu_from_ctr(self):
		"""Test manual detection from control item."""
		TestCase = collections.namedtuple("TestCase", "command, state, cb_on_called")

		test_cases = [
			TestCase("INCREASE", 30, True),
			TestCase("INCREASE", 40, False),
			TestCase("DECREASE", 20, False)
		]

		for test_case in test_cases:
			self._cb_on.reset_mock()
			self._cb_off.reset_mock()

			tests.helper.oh_item.item_command_event("Unittest_Dimmer_ctr", test_case.command)

			# cb_on called
			self.assertEqual(test_case.cb_on_called, self._cb_on.called)
			if test_case.cb_on_called:
				self._cb_on.assert_called_once_with(unittest.mock.ANY)

			# cb_off not called
			self._cb_off.assert_not_called()

			tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", test_case.state)
			self.assertEqual(test_case.state, self._observer_dimmer.value)

	def test_basic_behavior_on_knx(self):
		"""Test basic behavior. Switch ON via KNX"""
		# === Switch ON via KNX button ===
		# set initial state
		self._cb_on.reset_mock()
		self._observer_dimmer._value = 0
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0
		# In real system, this command is triggered about 2 sec later
		tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 100)
		self.assertEqual(100, self._observer_dimmer.value)
		self._cb_on.assert_called_once_with(unittest.mock.ANY)

		# === Switch ON via KNX value ===
		# set initial state
		self._cb_on.reset_mock()
		self._observer_dimmer._value = 0
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0
		# In real system, this command is triggered about 2 sec later
		tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 42)
		self.assertEqual(42, self._observer_dimmer.value)
		self._cb_on.assert_called_once_with(unittest.mock.ANY)

		# === Switch ON via KNX from group ===
		# set initial state
		self._cb_on.reset_mock()
		self._observer_dimmer._value = 0
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0
		# In real system, this command is triggered about 2 sec later
		tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 80)
		self.assertEqual(80, self._observer_dimmer.value)
		self._cb_on.assert_called_once_with(unittest.mock.ANY)

		# === Value via KNX from group ===
		# set initial state
		self._cb_on.reset_mock()
		self._observer_dimmer._value = 0
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0
		# In real system, this command is triggered about 2 sec later
		tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 60)
		self.assertEqual(60, self._observer_dimmer.value)
		self._cb_on.assert_called_once_with(unittest.mock.ANY)

	def test_manu_from_openhab(self):
		"""Test manual detection from control item."""
		TestCase = collections.namedtuple("TestCase", "command, state, cb_on_called, cb_off_called")
		self._observer_dimmer._StateObserverDimmer__last_received_value = 0

		test_cases = [
			TestCase(100, 100, True, False),
			TestCase(100, 100, False, False),
			TestCase(0, 0, False, True),
			TestCase("ON", 100.0, True, False),
			TestCase("OFF", 0.0, False, True),
		]

		for test_case in test_cases:
			self._cb_on.reset_mock()
			self._cb_off.reset_mock()
			tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", test_case.command)

			self.assertEqual(test_case.cb_on_called, self._cb_on.called)
			self.assertEqual(test_case.cb_off_called, self._cb_off.called)
			if test_case.cb_on_called:
				self._cb_on.assert_called_once_with(unittest.mock.ANY)
			if test_case.cb_off_called:
				self._cb_off.assert_called_once_with(unittest.mock.ANY)
			tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", test_case.state)
			self.assertEqual(test_case.state, self._observer_dimmer.value)

	def test_check_manual(self):
		"""Test method _check_manual."""

		TestCase = collections.namedtuple("TestCase", "event, current_value, on_called, off_called, change_called")

		test_cases = [
			TestCase(HABApp.openhab.events.ItemCommandEvent("any", "ON"), 0, True, False, False),
			TestCase(HABApp.openhab.events.ItemCommandEvent("any", "OFF"), 42, False, True, False),

			TestCase(HABApp.openhab.events.ItemCommandEvent("any", 0), 0, False, False, False),
			TestCase(HABApp.openhab.events.ItemCommandEvent("any", 42), 0, True, False, False),
			TestCase(HABApp.openhab.events.ItemCommandEvent("any", 0), 42, False, True, False),
			TestCase(HABApp.openhab.events.ItemCommandEvent("any", 42), 17, False, False, True),
			TestCase(HABApp.openhab.events.ItemCommandEvent("any", 42), 80, False, False, True)
		]

		with unittest.mock.patch.object(self._observer_dimmer, "_cb_on") as cb_on_mock, \
				unittest.mock.patch.object(self._observer_dimmer, "_cb_off") as cb_off_mock, \
				unittest.mock.patch.object(self._observer_dimmer, "_cb_brightness_change") as cb_change_mock:
			for test_case in test_cases:
				cb_on_mock.reset_mock()
				self._observer_dimmer._value = test_case.current_value
				cb_on_mock.reset_mock()
				cb_off_mock.reset_mock()
				cb_change_mock.reset_mock()

				self._observer_dimmer._check_manual(test_case.event)

				self.assertEqual(cb_on_mock.called, test_case.on_called)
				self.assertEqual(cb_off_mock.called, test_case.off_called)
				self.assertEqual(cb_change_mock.called, test_case.change_called)

				if test_case.on_called:
					cb_on_mock.assert_called_once_with(test_case.event)
				if test_case.off_called:
					cb_off_mock.assert_called_once_with(test_case.event)
				if test_case.change_called:
					cb_change_mock.assert_called_once_with(test_case.event)

	def test_cb_group_item(self):
		"""Test _cb_group_item."""
		self._observer_dimmer._group_last_event = 0
		with unittest.mock.patch("time.time") as time_mock, unittest.mock.patch.object(self._observer_dimmer, "_check_manual") as check_manual_mock:
			time_mock.return_value = 10
			self._observer_dimmer._cb_group_item(HABApp.openhab.events.ItemStateEvent("item_name", "ON"))
			time_mock.return_value = 10.2
			self._observer_dimmer._cb_group_item(HABApp.openhab.events.ItemStateEvent("item_name", "ON"))
		check_manual_mock.assert_called_once()

	def test_send_command_exception(self):
		"""Test if correct exceptions is raised."""
		with self.assertRaises(ValueError):
			self._observer_dimmer.send_command(None)

		with self.assertRaises(ValueError):
			self._observer_dimmer.send_command("dimmer")

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
