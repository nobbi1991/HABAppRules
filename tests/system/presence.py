"""Test Presence rule."""
import collections
import os
import pathlib
import sys
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.common.state_machine_rule
import habapp_rules.system.presence
import tests.common.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.timer


# pylint: disable=protected-access
class TestPresence(unittest.TestCase):
	"""Tests cases for testing presence rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
		self.addCleanup(self.send_command_mock_patcher.stop)
		self.send_command_mock = self.send_command_mock_patcher.start()

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door1", "CLOSED")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door2", "CLOSED")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Leaving", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone1", "ON")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone2", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_system_presence_Presence_state", "")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Presence", "ON")

		with unittest.mock.patch.object(habapp_rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_system_presence_Presence_state", "")):
			self._presence = habapp_rules.system.presence.Presence("Unittest_Presence", outside_door_names=["Unittest_Door1", "Unittest_Door2"], leaving_name="Unittest_Leaving", phone_names=["Unittest_Phone1", "Unittest_Phone2"])

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):
		"""Create state machine graph for documentation."""
		presence_graph = tests.common.graph_machines.GraphMachineTimer(  # pragma: no cover
			model=self._presence,
			states=self._presence.states,
			transitions=self._presence.trans,
			initial=self._presence.state,
			show_conditions=True)

		presence_graph.get_graph().draw(pathlib.Path(__file__).parent / "Presence.png", format="png", prog="dot")  # pragma: no cover

	def test_enums(self):
		"""Test if all enums from __init__.py are implemented"""
		implemented_states = list(self._presence.state_machine.states)
		enum_states = [state.value for state in habapp_rules.system.PresenceState]
		self.assertEqual(len(enum_states), len(implemented_states))
		self.assertTrue(all(state in enum_states for state in implemented_states))

	def test__init__(self):
		"""Test init."""
		tests.helper.oh_item.assert_value("rules_system_presence_Presence_state", "presence")
		self.assertEqual(self._presence.state, "presence")

	def test_get_initial_state(self):
		"""Test getting correct initial state."""
		Testcase = collections.namedtuple("Testcase", "presence, outside_doors, leaving, phones, expected_result")

		testcases = [
			# presence ON | leaving OFF
			Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=[], expected_result="presence"),
			Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["ON"], expected_result="presence"),
			Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["OFF"], expected_result="leaving"),
			Testcase(presence="ON", leaving="OFF", outside_doors=[], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=[], expected_result="presence"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["ON"], expected_result="presence"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["OFF"], expected_result="leaving"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=[], expected_result="presence"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["ON"], expected_result="presence"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["OFF"], expected_result="leaving"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="presence"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="presence"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="leaving"),
			Testcase(presence="ON", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="presence"),

			# presence ON | leaving ON
			Testcase(presence="ON", leaving="ON", outside_doors=[], phones=[], expected_result="leaving"),
			Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["ON"], expected_result="presence"),
			Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["OFF"], expected_result="leaving"),
			Testcase(presence="ON", leaving="ON", outside_doors=[], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=[], expected_result="leaving"),
			Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["ON"], expected_result="presence"),
			Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["OFF"], expected_result="leaving"),
			Testcase(presence="ON", leaving="ON", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=[], expected_result="leaving"),
			Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["ON"], expected_result="presence"),
			Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["OFF"], expected_result="leaving"),
			Testcase(presence="ON", leaving="ON", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="leaving"),
			Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="presence"),
			Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="leaving"),
			Testcase(presence="ON", leaving="ON", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="presence"),

			# presence OFF | leaving OFF
			Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=[], expected_result="absence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["ON"], expected_result="presence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["OFF"], expected_result="absence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=[], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=[], expected_result="absence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["ON"], expected_result="presence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["OFF"], expected_result="absence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["CLOSED"], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=[], expected_result="absence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["ON"], expected_result="presence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["OFF"], expected_result="absence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN"], phones=["ON", "OFF"], expected_result="presence"),

			Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=[], expected_result="absence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON"], expected_result="presence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["OFF"], expected_result="absence"),
			Testcase(presence="OFF", leaving="OFF", outside_doors=["OPEN, CLOSED"], phones=["ON", "OFF"], expected_result="presence"),

			# all None
			Testcase(presence=None, leaving=None, outside_doors=[None, None], phones=[None, None], expected_result="default"),
		]

		for testcase in testcases:
			self._presence._Presence__presence_item.value = testcase.presence
			self._presence._Presence__leaving_item.value = testcase.leaving

			self._presence._Presence__outside_door_items = [HABApp.openhab.items.ContactItem(f"Unittest_Door{idx}", state) for idx, state in enumerate(testcase.outside_doors)]
			self._presence._Presence__phone_items = [HABApp.openhab.items.SwitchItem(f"Unittest_Door{idx}", state) for idx, state in enumerate(testcase.phones)]

			self.assertEqual(self._presence._get_initial_state("default"), testcase.expected_result, f"failed testcase: {testcase}")

	def test_presence_trough_doors(self):
		"""Test if outside doors set presence correctly."""
		tests.helper.oh_item.send_command("Unittest_Presence", "OFF")
		self._presence.state_machine.set_state("absence")
		self.assertEqual(self._presence.state, "absence")

		self.__runner.process_events()
		tests.helper.oh_item.send_command("Unittest_Door1", "CLOSED", "CLOSED")
		self.assertEqual(self._presence.state, "absence")

		tests.helper.oh_item.send_command("Unittest_Door1", "OPEN", "CLOSED")
		self.assertEqual(self._presence.state, "presence")
		tests.helper.oh_item.assert_value("Unittest_Presence", "ON")

		tests.helper.oh_item.send_command("Unittest_Door1", "OPEN", "CLOSED")
		self.assertEqual(self._presence.state, "presence")

		tests.helper.oh_item.send_command("Unittest_Door1", "CLOSED", "CLOSED")
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
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual(self._presence.state, "absence")

	def test_abort_leaving(self):
		"""Test aborting of leaving state."""
		self._presence.state_machine.set_state("presence")
		self.assertEqual(self._presence.state, "presence")
		tests.helper.oh_item.set_state("Unittest_Leaving", "ON")

		tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
		self.assertEqual(self._presence.state, "leaving")
		tests.helper.oh_item.assert_value("Unittest_Leaving", "ON")

		tests.helper.oh_item.send_command("Unittest_Leaving", "OFF", "ON")
		self.assertEqual(self._presence.state, "presence")
		tests.helper.oh_item.assert_value("Unittest_Leaving", "OFF")

	def test_abort_leaving_after_last_phone(self):
		"""Test aborting of leaving which was started through last phone leaving."""
		self._presence.state_machine.set_state("presence")
		tests.helper.oh_item.set_state("Unittest_Phone1", "ON")

		tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
		tests.helper.timer.call_timeout(self.threading_timer_mock)
		self.assertEqual(self._presence.state, "leaving")
		tests.helper.oh_item.assert_value("Unittest_Leaving", "ON")

		tests.helper.oh_item.send_command("Unittest_Leaving", "OFF", "ON")
		self.assertEqual(self._presence.state, "presence")

		tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
		self.assertEqual(self._presence.state, "presence")

		tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
		tests.helper.timer.call_timeout(self.threading_timer_mock)
		self.assertEqual(self._presence.state, "leaving")
		tests.helper.oh_item.assert_value("Unittest_Leaving", "ON")

	def test_leaving_with_phones(self):
		"""Test if leaving and absence is correct if phones appear/disappear during or after leaving."""
		# set initial states
		tests.helper.oh_item.set_state("Unittest_Phone1", "ON")
		tests.helper.oh_item.set_state("Unittest_Phone2", "OFF")
		self._presence.state_machine.set_state("presence")
		tests.helper.oh_item.send_command("Unittest_Leaving", "ON", "OFF")
		self.assertEqual(self._presence.state, "leaving")

		# leaving on, last phone disappears
		tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
		self.assertEqual(self._presence.state, "leaving")

		# leaving on, first phone appears
		tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
		self.assertEqual(self._presence.state, "leaving")

		# leaving on, second phone appears
		tests.helper.oh_item.send_command("Unittest_Phone2", "ON", "OFF")
		self.assertEqual(self._presence.state, "leaving")

		# leaving on, both phones leaving
		tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
		tests.helper.oh_item.send_command("Unittest_Phone2", "OFF", "ON")
		self.assertEqual(self._presence.state, "leaving")

		# absence on, one disappears, one stays online
		tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Phone2", "ON", "OFF")
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual(self._presence.state, "absence")
		tests.helper.oh_item.send_command("Unittest_Phone1", "OFF", "ON")
		self.assertEqual(self._presence.state, "absence")

		# absence on, two phones disappears
		tests.helper.oh_item.send_command("Unittest_Phone2", "OFF", "ON")
		self.assertEqual(self._presence.state, "absence")

	def test__set_leaving_through_phone(self):
		"""Test if leaving_detected is called correctly after timeout of __phone_absence_timer."""
		TestCase = collections.namedtuple("TestCase", "state, leaving_detected_called")

		test_cases = [
			TestCase("presence", True),
			TestCase("leaving", False),
			TestCase("absence", False),
			TestCase("long_absence", False)
		]

		for test_case in test_cases:
			with unittest.mock.patch.object(self._presence, "leaving_detected") as leaving_detected_mock:
				self._presence.state = test_case.state
				self._presence._Presence__set_leaving_through_phone()
			self.assertEqual(test_case.leaving_detected_called, leaving_detected_mock.called)

	# pylint: disable=no-member
	def test_long_absence(self):
		"""Test entering long_absence and leaving it."""
		# set initial state
		self._presence.state_machine.set_state("presence")
		tests.helper.oh_item.set_state("Unittest_Presence", "ON")

		# go to absence
		self._presence.absence_detected()
		self.assertEqual(self._presence.state, "absence")
		tests.helper.oh_item.assert_value("Unittest_Presence", "OFF")

		# check if timeout started, and stop the mocked timer
		self.transitions_timer_mock.assert_called_with(1.5 * 24 * 3600, unittest.mock.ANY, args=unittest.mock.ANY)
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual(self._presence.state, "long_absence")
		tests.helper.oh_item.assert_value("Unittest_Presence", "OFF")

		# check if presence is set after door open
		self._presence._cb_outside_door(HABApp.openhab.events.ItemStateChangedEvent("Unittest_Door1", "OPEN", "CLOSED"))
		self.assertEqual(self._presence.state, "presence")
		tests.helper.oh_item.assert_value("Unittest_Presence", "ON")

	def test_manual_change(self):
		"""Test if change of presence object is setting correct state."""
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
		self.threading_timer_mock.assert_called_once_with(1200, self._presence._Presence__set_leaving_through_phone)
		tests.helper.timer.call_timeout(self.threading_timer_mock)
		self.assertEqual(self._presence.state, "leaving")

		# phone appears during leaving -> leaving expected
		tests.helper.oh_item.send_command("Unittest_Phone1", "ON", "OFF")
		self.assertEqual(self._presence.state, "leaving")
		self.assertIsNone(self._presence._Presence__phone_absence_timer)

		# timeout is over -> absence expected
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual(self._presence.state, "absence")

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
