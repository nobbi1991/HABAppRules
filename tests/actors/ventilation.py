"""Test ventilation rules."""
import collections
import datetime
import os
import pathlib
import sys
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.config.shading
import habapp_rules.actors.config.ventilation
import habapp_rules.actors.light
import habapp_rules.actors.shading
import habapp_rules.actors.state_observer
import habapp_rules.actors.ventilation
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer


# pylint: disable=protected-access,no-member,too-many-public-methods
class TestVentilation(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing Ventilation."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		self.run_at_mock_patcher = unittest.mock.patch("HABApp.rule.scheduler.habappschedulerview.HABAppSchedulerView.at")
		self.addCleanup(self.run_at_mock_patcher.stop)
		self.run_at_mock = self.run_at_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_min_level", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_manual", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Ventilation_min_level_state", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_max_level", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_manual", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_Custom_State", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_hand_request", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_external_request", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_on", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_power", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_display_text", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", None)

		config_max = habapp_rules.actors.config.ventilation.VentilationConfig(
			habapp_rules.actors.config.ventilation.StateConfig(101, "Normal Custom"),
			habapp_rules.actors.config.ventilation.StateConfigWithTimeout(102, "Hand Custom", 42 * 60),
			habapp_rules.actors.config.ventilation.StateConfig(103, "External Custom"),
			habapp_rules.actors.config.ventilation.StateConfig(104, "Humidity Custom"),
			habapp_rules.actors.config.ventilation.StateConfigLongAbsence(105, "Absence Custom", 1800, datetime.time(18))
		)

		self.ventilation_min = habapp_rules.actors.ventilation.Ventilation("Unittest_Ventilation_min_level", "Unittest_Ventilation_min_manual", habapp_rules.actors.config.ventilation.CONFIG_DEFAULT)
		self.ventilation_max = habapp_rules.actors.ventilation.Ventilation(
			"Unittest_Ventilation_max_level",
			"Unittest_Ventilation_max_manual",
			config_max,
			"Unittest_Ventilation_max_hand_request",
			"Unittest_Ventilation_max_external_request",
			"Unittest_Presence_state",
			"Unittest_Ventilation_max_feedback_on",
			"Unittest_Ventilation_max_feedback_power",
			"Unittest_Ventilation_max_display_text",
			"Unittest_Ventilation_max_Custom_State")

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):  # pragma: no cover
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "Ventilation_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)

		graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
			model=tests.helper.graph_machines.FakeModel(),
			states=self.ventilation_min.states,
			transitions=self.ventilation_min.trans,
			initial=self.ventilation_min.state,
			show_conditions=False)

		graph.get_graph().draw(picture_dir / "Ventilation.png", format="png", prog="dot")

		for state_name in [state for state in self._get_state_names(self.ventilation_min.states) if state not in ["auto_init"]]:
			graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
				model=tests.helper.graph_machines.FakeModel(),
				states=self.ventilation_min.states,
				transitions=self.ventilation_min.trans,
				initial=state_name,
				show_conditions=True)
			graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Ventilation_{state_name}.png", format="png", prog="dot")

	def test_init(self):
		"""Test __init__."""
		# check timeouts
		self.assertEqual(3600, self.ventilation_min.state_machine.get_state("Auto_PowerHand").timeout)
		self.assertEqual(3600, self.ventilation_min.state_machine.get_state("Auto_LongAbsence_On").timeout)

		self.assertEqual(42 * 60, self.ventilation_max.state_machine.get_state("Auto_PowerHand").timeout)
		self.assertEqual(1800, self.ventilation_max.state_machine.get_state("Auto_LongAbsence_On").timeout)

	def test_get_initial_state(self):
		"""Test getting initial state."""
		TestCase = collections.namedtuple("TestCase", "presence_state, manual, hand_request, external_request, expected_state_min, expected_state_max")

		test_cases = [
			# present
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, False, False, False, "Auto_Normal", "Auto_Normal"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, False, False, True, "Auto_Normal", "Auto_PowerExternal"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, False, True, False, "Auto_Normal", "Auto_PowerHand"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, False, True, True, "Auto_Normal", "Auto_PowerHand"),

			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, True, False, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, True, False, True, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, True, True, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, True, True, True, "Manual", "Manual"),

			# long absence
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, False, False, False, "Auto_Normal", "Auto_LongAbsence"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, False, False, True, "Auto_Normal", "Auto_LongAbsence"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, False, True, False, "Auto_Normal", "Auto_PowerHand"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, False, True, True, "Auto_Normal", "Auto_PowerHand"),

			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, True, False, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, True, False, True, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, True, True, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, True, True, True, "Manual", "Manual"),
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				tests.helper.oh_item.set_state("Unittest_Ventilation_min_manual", "ON" if test_case.manual else "OFF")
				tests.helper.oh_item.set_state("Unittest_Ventilation_max_manual", "ON" if test_case.manual else "OFF")
				tests.helper.oh_item.set_state("Unittest_Ventilation_max_hand_request", "ON" if test_case.hand_request else "OFF")
				tests.helper.oh_item.set_state("Unittest_Ventilation_max_external_request", "ON" if test_case.external_request else "OFF")
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_state)

				self.assertEqual(test_case.expected_state_min, self.ventilation_min._get_initial_state())
				self.assertEqual(test_case.expected_state_max, self.ventilation_max._get_initial_state())

	def test_set_level(self):
		"""test _set_level."""
		TestCase = collections.namedtuple("TestCase", "state, expected_level")

		test_cases = [
			TestCase("Manual", None),
			TestCase("Auto_PowerHand", 102),
			TestCase("Auto_Normal", 101),
			TestCase("Auto_PowerExternal", 103),
			TestCase("Auto_LongAbsence_On", 105),
			TestCase("Auto_LongAbsence_Off", 0),
			TestCase("Auto_Init", None),
		]

		with unittest.mock.patch("habapp_rules.core.helper.send_if_different") as send_mock:
			for test_case in test_cases:
				with self.subTest(test_case=test_case):
					send_mock.reset_mock()
					self.ventilation_max.state = test_case.state

					self.ventilation_max._set_level()

					if test_case.expected_level is not None:
						send_mock.assert_called_once_with(self.ventilation_max._item_ventilation_level, test_case.expected_level)
					else:
						send_mock.assert_not_called()

	def test_set_feedback_states(self):
		"""test _set_feedback_states."""
		TestCase = collections.namedtuple("TestCase", "ventilation_level, state, expected_on, expected_power, expected_display_text")

		test_cases = [
			TestCase(None, "Auto_PowerHand", False, False, "Hand Custom 42min"),
			TestCase(None, "Auto_Normal", False, False, "Normal Custom"),
			TestCase(None, "Auto_PowerExternal", False, False, "External Custom"),
			TestCase(None, "Auto_LongAbsence_On", False, False, "Absence Custom ON"),
			TestCase(None, "Auto_LongAbsence_Off", False, False, "Absence Custom OFF"),
			TestCase(None, "Auto_Init", False, False, "Absence Custom OFF"),

			TestCase(0, "Auto_PowerHand", False, False, "Hand Custom 42min"),
			TestCase(0, "Auto_Normal", False, False, "Normal Custom"),
			TestCase(0, "Auto_PowerExternal", False, False, "External Custom"),
			TestCase(0, "Auto_LongAbsence_On", False, False, "Absence Custom ON"),
			TestCase(0, "Auto_LongAbsence_Off", False, False, "Absence Custom OFF"),
			TestCase(0, "Auto_Init", False, False, "Absence Custom OFF"),

			TestCase(1, "Auto_PowerHand", True, False, "Hand Custom 42min"),
			TestCase(1, "Auto_Normal", True, False, "Normal Custom"),
			TestCase(1, "Auto_PowerExternal", True, False, "External Custom"),
			TestCase(1, "Auto_LongAbsence_On", True, False, "Absence Custom ON"),
			TestCase(1, "Auto_LongAbsence_Off", True, False, "Absence Custom OFF"),
			TestCase(1, "Auto_Init", True, False, "Absence Custom OFF"),

			TestCase(2, "Auto_PowerHand", True, True, "Hand Custom 42min"),
			TestCase(2, "Auto_Normal", True, True, "Normal Custom"),
			TestCase(2, "Auto_PowerExternal", True, True, "External Custom"),
			TestCase(2, "Auto_LongAbsence_On", True, True, "Absence Custom ON"),
			TestCase(2, "Auto_LongAbsence_Off", True, True, "Absence Custom OFF"),
			TestCase(2, "Auto_Init", True, True, "Absence Custom OFF"),

			TestCase(42, "Auto_PowerHand", True, True, "Hand Custom 42min"),
			TestCase(42, "Auto_Normal", True, True, "Normal Custom"),
			TestCase(42, "Auto_PowerExternal", True, True, "External Custom"),
			TestCase(42, "Auto_LongAbsence_On", True, True, "Absence Custom ON"),
			TestCase(42, "Auto_LongAbsence_Off", True, True, "Absence Custom OFF"),
			TestCase(42, "Auto_Init", True, True, "Absence Custom OFF"),
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self.ventilation_min._ventilation_level = test_case.ventilation_level
				self.ventilation_max._ventilation_level = test_case.ventilation_level
				self.ventilation_min.state = test_case.state
				self.ventilation_max.state = test_case.state

				self.ventilation_min._set_feedback_states()
				self.ventilation_max._set_feedback_states()

				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_on", "ON" if test_case.expected_on else "OFF")
				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_power", "ON" if test_case.expected_power else "OFF")
				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_display_text", test_case.expected_display_text)

	def test_on_enter_long_absence_off(self):
		"""Test on_enter_Auto_LongAbsence_Off."""
		self.ventilation_max.to_Auto_LongAbsence_Off()
		self.run_at_mock.assert_called_once_with(datetime.time(18), self.ventilation_max._long_absence_power_on)

	def test__set_hand_display_text(self):
		"""test __set_hand_display_text."""
		# wrong state
		for state in ["Manual", "Auto_Normal", "Auto_PowerHumidity", "Auto_PowerDryer", "Auto_LongAbsence_On", "Auto_LongAbsence_Off"]:
			self.ventilation_max.state = state

			self.ventilation_max._VentilationBase__set_hand_display_text()
			self.run_at_mock.assert_not_called()

		# PowerHand state:
		TestCase = collections.namedtuple("TestCase", "changed_time, now_time, expected_display")

		test_cases = [
			TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 0), "Hand Custom 42min"),
			TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 0, 30), "Hand Custom 42min"),
			TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 0, 31), "Hand Custom 41min"),
			TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 2, 0), "Hand Custom 40min"),
			TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 2, 31), "Hand Custom 39min"),
			TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 42, 0), "Hand Custom 0min"),
			TestCase(datetime.datetime(2024, 1, 1, 12), datetime.datetime(2024, 1, 1, 12, 45, 0), "Hand Custom 0min"),
		]

		self.ventilation_max.state = "Auto_PowerHand"

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self.ventilation_max._state_change_time = test_case.changed_time
				now_value = test_case.now_time
				self.run_at_mock.reset_mock()
				with unittest.mock.patch("datetime.datetime") as datetime_mock:
					datetime_mock.now.return_value = now_value
					self.ventilation_max._VentilationBase__set_hand_display_text()
				self.run_at_mock.assert_called_once()
				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_display_text", test_case.expected_display)

	def test_external_active_and_configured(self):
		"""test _external_active_and_configured."""
		self.assertFalse(self.ventilation_min._external_active_and_configured())

		tests.helper.oh_item.set_state("Unittest_Ventilation_max_external_request", "OFF")
		self.assertFalse(self.ventilation_max._external_active_and_configured())

		tests.helper.oh_item.set_state("Unittest_Ventilation_max_external_request", "ON")
		self.assertTrue(self.ventilation_max._external_active_and_configured())

	def test_auto_normal_transitions(self):
		"""Test transitions of state Auto_Normal"""
		# to Auto_PowerHand
		self.ventilation_min.to_Auto_Normal()
		self.ventilation_max.to_Auto_Normal()

		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

		# back to Auto_Normal
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

		# to Auto_PowerExternal
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

		# back to Auto_Normal
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "OFF")

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

		# to Auto_LongAbsence
		tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", habapp_rules.system.PresenceState.LONG_ABSENCE.value)

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_LongAbsence_Off", self.ventilation_max.state)

		# back to Auto_Normal
		tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

	def test_auto_power_external_transitions(self):
		"""Test transitions of state Auto_PowerExternal"""
		# to Auto_PowerExternal
		self.ventilation_max.to_Auto_PowerExternal()
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "OFF")
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

		# back to AutoPowerExternal
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
		self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

		# to Auto_PowerHand
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
		self.assertEqual("Auto_PowerHand", self.ventilation_max.state)
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
		self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

		# back to AutoPowerExternal
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")
		self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

		# to Auto_LongAbsence
		tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", habapp_rules.system.PresenceState.LONG_ABSENCE.value)
		self.assertEqual("Auto_LongAbsence_Off", self.ventilation_max.state)

	def test_auto_power_hand_transitions(self):
		"""Test transitions of state Auto_PowerHand"""
		# set Auto_LongAbsence as initial state
		self.ventilation_max.to_Auto_LongAbsence_On()

		# to Auto_PowerHand
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
		self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

		# to Auto_Normal (external request is not ON)
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

		# back to Auto_PowerHand
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
		self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

		# to Auto_PowerExternal
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")
		self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

		# back to Auto_PowerHand
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
		self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

		# timeout
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "OFF")
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)
		tests.helper.oh_item.assert_value("Unittest_Ventilation_max_hand_request", "OFF")

	def test_manual_transitions(self):
		"""Test transitions of state Manual."""
		# set Auto as initial state
		self.ventilation_min.to_Auto_Normal()
		self.ventilation_max.to_Auto_Normal()

		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_min_manual", "ON")
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_manual", "ON")

		self.assertEqual("Manual", self.ventilation_min.state)
		self.assertEqual("Manual", self.ventilation_max.state)

		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_min_manual", "OFF")
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_manual", "OFF")

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)


class TestVentilationHeliosTwoStage(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing VentilationHeliosTwoStage."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_output_on", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_output_power", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_manual", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Ventilation_min_output_on_state", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_output_on", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_output_power", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_manual", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_Custom_State", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_hand_request", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_external_request", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_on", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_power", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_display_text", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", None)

		config_max = habapp_rules.actors.config.ventilation.VentilationConfig(
			habapp_rules.actors.config.ventilation.StateConfig(101, "Normal Custom"),
			habapp_rules.actors.config.ventilation.StateConfigWithTimeout(102, "Hand Custom", 42 * 60),
			habapp_rules.actors.config.ventilation.StateConfig(103, "External Custom"),
			habapp_rules.actors.config.ventilation.StateConfig(104, "Humidity Custom"),
			habapp_rules.actors.config.ventilation.StateConfigLongAbsence(105, "Absence Custom", 1800, datetime.time(18)),
			habapp_rules.actors.config.ventilation.StateConfig(99, "AfterRun Custom")
		)

		self.ventilation_min = habapp_rules.actors.ventilation.VentilationHeliosTwoStage(
			"Unittest_Ventilation_min_output_on",
			"Unittest_Ventilation_min_output_power",
			"Unittest_Ventilation_min_manual",
			habapp_rules.actors.config.ventilation.CONFIG_DEFAULT
		)
		self.ventilation_max = habapp_rules.actors.ventilation.VentilationHeliosTwoStage(
			"Unittest_Ventilation_max_output_on",
			"Unittest_Ventilation_max_output_power",
			"Unittest_Ventilation_max_manual",
			config_max,
			"Unittest_Ventilation_max_hand_request",
			"Unittest_Ventilation_max_external_request",
			"Unittest_Presence_state",
			"Unittest_Ventilation_max_feedback_on",
			"Unittest_Ventilation_max_feedback_power",
			"Unittest_Ventilation_max_display_text",
			350,
			"Unittest_Ventilation_max_Custom_State")

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):  # pragma: no cover
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "VentilationHeliosTwoStage_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)

		graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
			model=tests.helper.graph_machines.FakeModel(),
			states=self.ventilation_min.states,
			transitions=self.ventilation_min.trans,
			initial=self.ventilation_min.state,
			show_conditions=False)

		graph.get_graph().draw(picture_dir / "Ventilation.png", format="png", prog="dot")

		for state_name in [state for state in self._get_state_names(self.ventilation_min.states) if state not in ["auto_init"]]:
			graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
				model=tests.helper.graph_machines.FakeModel(),
				states=self.ventilation_min.states,
				transitions=self.ventilation_min.trans,
				initial=state_name,
				show_conditions=True)
			graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Ventilation_{state_name}.png", format="png", prog="dot")

	def test_set_level(self):
		"""test _set_level."""
		TestCase = collections.namedtuple("TestCase", "state, expected_on, expected_power")

		test_cases = [
			TestCase("Manual", None, None),
			TestCase("Auto_PowerHand", "ON", "ON"),
			TestCase("Auto_Normal", "ON", "OFF"),
			TestCase("Auto_PowerExternal", "ON", "ON"),
			TestCase("Auto_LongAbsence_On", "ON", "ON"),
			TestCase("Auto_LongAbsence_Off", "OFF", "OFF"),
			TestCase("Auto_Init", None, None),
			TestCase("Auto_PowerAfterRun", "ON", "OFF"),
		]

		self.ventilation_max._config.state_normal.level = 1

		with unittest.mock.patch("habapp_rules.core.helper.send_if_different") as send_mock:
			for test_case in test_cases:
				with self.subTest(test_case=test_case):
					send_mock.reset_mock()
					self.ventilation_max.state = test_case.state

					self.ventilation_max._set_level()

					if test_case.expected_on is not None:
						send_mock.assert_any_call(self.ventilation_max._item_ventilation_on, test_case.expected_on)

					if test_case.expected_power is not None:
						send_mock.assert_any_call(self.ventilation_max._item_ventilation_power, test_case.expected_power)

	def test_set_feedback_states(self):
		"""test _set_feedback_states."""
		TestCase = collections.namedtuple("TestCase", "ventilation_level, state, expected_on, expected_power, expected_display_text")

		test_cases = [
			TestCase(None, "Auto_PowerAfterRun", False, False, "AfterRun Custom"),
			TestCase(0, "Auto_PowerAfterRun", False, False, "AfterRun Custom"),
			TestCase(1, "Auto_PowerAfterRun", True, False, "AfterRun Custom")
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self.ventilation_min._ventilation_level = test_case.ventilation_level
				self.ventilation_max._ventilation_level = test_case.ventilation_level
				self.ventilation_min.state = test_case.state
				self.ventilation_max.state = test_case.state

				self.ventilation_min._set_feedback_states()
				self.ventilation_max._set_feedback_states()

				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_on", "ON" if test_case.expected_on else "OFF")
				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_power", "ON" if test_case.expected_power else "OFF")
				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_display_text", test_case.expected_display_text)

	def test_power_after_run_transitions(self):
		"""Test transitions of PowerAfterRun."""
		# PowerAfterRun to PowerHand
		self.ventilation_max.to_Auto_PowerAfterRun()
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
		self.assertEqual("Auto_PowerHand", self.ventilation_max.state)

		# back to PowerAfterRun
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")
		self.assertEqual("Auto_PowerAfterRun", self.ventilation_max.state)

		# PowerAfterRun to PowerExternal
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
		self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)

		# back to PowerAfterRun
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "OFF")
		self.assertEqual("Auto_PowerAfterRun", self.ventilation_max.state)

		# timeout of PowerAfterRun
		tests.helper.timer.call_timeout(self.transitions_timer_mock)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)


class TestVentilationHeliosTwoStageHumidity(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing VentilationHeliosTwoStageHumidity."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_output_on", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_output_power", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_min_current", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_min_manual", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Ventilation_min_output_on_state", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_output_on", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_output_power", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Ventilation_max_current", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_manual", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_Custom_State", None)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_hand_request", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_external_request", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_on", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Ventilation_max_feedback_power", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Ventilation_max_display_text", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", None)

		config_max = habapp_rules.actors.config.ventilation.VentilationConfig(
			habapp_rules.actors.config.ventilation.StateConfig(101, "Normal Custom"),
			habapp_rules.actors.config.ventilation.StateConfigWithTimeout(102, "Hand Custom", 42 * 60),
			habapp_rules.actors.config.ventilation.StateConfig(103, "External Custom"),
			habapp_rules.actors.config.ventilation.StateConfig(104, "Humidity Custom"),
			habapp_rules.actors.config.ventilation.StateConfigLongAbsence(105, "Absence Custom", 1800, datetime.time(18))
		)

		self.ventilation_min = habapp_rules.actors.ventilation.VentilationHeliosTwoStageHumidity(
			"Unittest_Ventilation_min_output_on",
			"Unittest_Ventilation_min_output_power",
			"Unittest_Ventilation_min_current",
			"Unittest_Ventilation_min_manual",
			habapp_rules.actors.config.ventilation.CONFIG_DEFAULT
		)
		self.ventilation_max = habapp_rules.actors.ventilation.VentilationHeliosTwoStageHumidity(
			"Unittest_Ventilation_max_output_on",
			"Unittest_Ventilation_max_output_power",
			"Unittest_Ventilation_max_current",
			"Unittest_Ventilation_max_manual",
			config_max,
			"Unittest_Ventilation_max_hand_request",
			"Unittest_Ventilation_max_external_request",
			"Unittest_Presence_state",
			"Unittest_Ventilation_max_feedback_on",
			"Unittest_Ventilation_max_feedback_power",
			"Unittest_Ventilation_max_display_text",
			350,
			0.5,
			"Unittest_Ventilation_max_Custom_State")

	def test_set_level(self):
		"""test _set_level."""
		TestCase = collections.namedtuple("TestCase", "state, expected_on, expected_power")

		test_cases = [
			TestCase("Manual", None, None),
			TestCase("Auto_PowerHand", "ON", "ON"),
			TestCase("Auto_Normal", "ON", "OFF"),
			TestCase("Auto_PowerExternal", "ON", "ON"),
			TestCase("Auto_LongAbsence_On", "ON", "ON"),
			TestCase("Auto_LongAbsence_Off", "OFF", "OFF"),
			TestCase("Auto_Init", None, None),
			TestCase("Auto_PowerAfterRun", "ON", "OFF"),
		]

		self.ventilation_max._config.state_normal.level = 1

		with unittest.mock.patch("habapp_rules.core.helper.send_if_different") as send_mock:
			for test_case in test_cases:
				with self.subTest(test_case=test_case):
					send_mock.reset_mock()
					self.ventilation_max.state = test_case.state

					self.ventilation_max._set_level()

					if test_case.expected_on is not None:
						send_mock.assert_any_call(self.ventilation_max._item_ventilation_on, test_case.expected_on)

					if test_case.expected_power is not None:
						send_mock.assert_any_call(self.ventilation_max._item_ventilation_power, test_case.expected_power)

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):  # pragma: no cover
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "VentilationHeliosTwoStageHumidity_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)

		graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
			model=tests.helper.graph_machines.FakeModel(),
			states=self.ventilation_min.states,
			transitions=self.ventilation_min.trans,
			initial=self.ventilation_min.state,
			show_conditions=False)

		graph.get_graph().draw(picture_dir / "Ventilation.png", format="png", prog="dot")

		for state_name in [state for state in self._get_state_names(self.ventilation_min.states) if state not in ["auto_init"]]:
			graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
				model=tests.helper.graph_machines.FakeModel(),
				states=self.ventilation_min.states,
				transitions=self.ventilation_min.trans,
				initial=state_name,
				show_conditions=True)
			graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Ventilation_{state_name}.png", format="png", prog="dot")

	def test_get_initial_state(self):
		"""Test _get_initial_state."""
		TestCase = collections.namedtuple("TestCase", "presence_state, current, manual, hand_request, external_request, expected_state_min, expected_state_max")

		test_cases = [
			# present | current = None
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, False, False, False, "Auto_Normal", "Auto_Normal"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, False, False, True, "Auto_Normal", "Auto_PowerExternal"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, False, True, False, "Auto_Normal", "Auto_PowerHand"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, False, True, True, "Auto_Normal", "Auto_PowerHand"),

			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, True, False, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, True, False, True, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, True, True, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, None, True, True, True, "Manual", "Manual"),

			# present | current smaller than the threshold
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, False, False, False, "Auto_Normal", "Auto_Normal"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, False, False, True, "Auto_Normal", "Auto_PowerExternal"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, False, True, False, "Auto_Normal", "Auto_PowerHand"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, False, True, True, "Auto_Normal", "Auto_PowerHand"),

			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, True, False, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, True, False, True, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, True, True, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 0.01, True, True, True, "Manual", "Manual"),

			# present | current greater than the threshold
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, False, False, False, "Auto_Normal", "Auto_PowerHumidity"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, False, False, True, "Auto_Normal", "Auto_PowerExternal"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, False, True, False, "Auto_Normal", "Auto_PowerHand"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, False, True, True, "Auto_Normal", "Auto_PowerHand"),

			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, True, False, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, True, False, True, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, True, True, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.PRESENCE.value, 1, True, True, True, "Manual", "Manual"),

			# long absence
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, False, False, False, "Auto_Normal", "Auto_LongAbsence"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, False, False, True, "Auto_Normal", "Auto_LongAbsence"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, False, True, False, "Auto_Normal", "Auto_PowerHand"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, False, True, True, "Auto_Normal", "Auto_PowerHand"),

			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, True, False, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, True, False, True, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, True, True, False, "Manual", "Manual"),
			TestCase(habapp_rules.system.PresenceState.LONG_ABSENCE.value, 20, True, True, True, "Manual", "Manual"),
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				tests.helper.oh_item.set_state("Unittest_Ventilation_min_manual", "ON" if test_case.manual else "OFF")
				tests.helper.oh_item.set_state("Unittest_Ventilation_max_manual", "ON" if test_case.manual else "OFF")
				tests.helper.oh_item.set_state("Unittest_Ventilation_max_current", test_case.current)
				tests.helper.oh_item.set_state("Unittest_Ventilation_max_hand_request", "ON" if test_case.hand_request else "OFF")
				tests.helper.oh_item.set_state("Unittest_Ventilation_max_external_request", "ON" if test_case.external_request else "OFF")
				tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_state)

				self.assertEqual(test_case.expected_state_min, self.ventilation_min._get_initial_state())
				self.assertEqual(test_case.expected_state_max, self.ventilation_max._get_initial_state())


	def test_set_feedback_states(self):
		"""test _set_feedback_states."""
		TestCase = collections.namedtuple("TestCase", "ventilation_level, state, expected_on, expected_power, expected_display_text")

		test_cases = [
			TestCase(None, "Auto_PowerHumidity", False, False, "Humidity Custom"),
			TestCase(0, "Auto_PowerHumidity", False, False, "Humidity Custom"),
			TestCase(1, "Auto_PowerHumidity", True, False, "Humidity Custom")
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self.ventilation_min._ventilation_level = test_case.ventilation_level
				self.ventilation_max._ventilation_level = test_case.ventilation_level
				self.ventilation_min.state = test_case.state
				self.ventilation_max.state = test_case.state

				self.ventilation_min._set_feedback_states()
				self.ventilation_max._set_feedback_states()

				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_on", "ON" if test_case.expected_on else "OFF")
				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_feedback_power", "ON" if test_case.expected_power else "OFF")
				tests.helper.oh_item.assert_value("Unittest_Ventilation_max_display_text", test_case.expected_display_text)

	def test_current_greater_threshold(self):
		"""Test __current_greater_threshold."""

		TestCase = collections.namedtuple("TestCase", "threshold, item_value, given_value, expected_result")

		test_cases = [
			TestCase(42, 0, 0, False),
			TestCase(42, 0, 100, True),
			TestCase(42, 100, 0, False),
			TestCase(42, 100, 100, True),

			TestCase(42, 0, None, False),
			TestCase(42, 100, None, True),
			TestCase(42, None, None, False)
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self.ventilation_max._current_threshold_power = test_case.threshold
				tests.helper.oh_item.set_state("Unittest_Ventilation_max_current", test_case.item_value)

				result = self.ventilation_max._current_greater_threshold() if test_case.given_value is None else self.ventilation_max._current_greater_threshold(test_case.given_value)

				self.assertEqual(test_case.expected_result, result)

	def test_power_after_run_transitions(self):
		"""Test transitions of PowerAfterRun."""
		# _end_after_run triggered
		self.ventilation_max.to_Auto_PowerAfterRun()
		self.ventilation_max._end_after_run()
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

	def test_power_humidity_transitions(self):
		"""Test transitions of state Auto_PowerHumidity."""
		# set AutoNormal as initial state
		self.ventilation_min.to_Auto_Normal()
		self.ventilation_max.to_Auto_Normal()

		# state != Auto_PowerHumidity | current below the threshold
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.1)
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.1)

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

		# state != Auto_PowerHumidity | current grater then the threshold
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.2)
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.6)

		self.assertEqual("Auto_PowerHumidity", self.ventilation_min.state)
		self.assertEqual("Auto_PowerHumidity", self.ventilation_max.state)

		# state == Auto_PowerHumidity | current grater then the threshold
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.2)
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.6)

		self.assertEqual("Auto_PowerHumidity", self.ventilation_min.state)
		self.assertEqual("Auto_PowerHumidity", self.ventilation_max.state)

		# state == Auto_PowerHumidity | current below then the threshold
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.1)
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.1)

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

		# state == Auto_PowerAfterRun | current below the threshold
		self.ventilation_min.to_Auto_PowerAfterRun()
		self.ventilation_max.to_Auto_PowerAfterRun()

		tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.1)
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.1)

		self.ventilation_min._after_run_timeout()
		self.ventilation_max._after_run_timeout()

		self.assertEqual("Auto_Normal", self.ventilation_min.state)
		self.assertEqual("Auto_Normal", self.ventilation_max.state)

		# state == Auto_PowerAfterRun | current grater then the threshold
		self.ventilation_min.to_Auto_PowerAfterRun()
		self.ventilation_max.to_Auto_PowerAfterRun()

		tests.helper.oh_item.item_state_event("Unittest_Ventilation_min_current", 0.2)
		tests.helper.oh_item.item_state_event("Unittest_Ventilation_max_current", 0.6)

		self.ventilation_min._after_run_timeout()
		self.ventilation_max._after_run_timeout()

		self.assertEqual("Auto_PowerHumidity", self.ventilation_min.state)
		self.assertEqual("Auto_PowerHumidity", self.ventilation_max.state)

		# state == Auto_PowerHumidity | _hand_on triggered
		self.ventilation_max.to_Auto_PowerHumidity()
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "ON")
		self.assertEqual("Auto_PowerHand", self.ventilation_max.state)
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_hand_request", "OFF")

		# state == Auto_PowerHumidity | _external_on triggered
		self.ventilation_max.to_Auto_PowerHumidity()
		tests.helper.oh_item.item_state_change_event("Unittest_Ventilation_max_external_request", "ON")
		self.assertEqual("Auto_PowerExternal", self.ventilation_max.state)
