"""Test shading rules."""
import collections
import copy
import os
import pathlib
import sys
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.actors.config.shading
import habapp_rules.actors.light
import habapp_rules.actors.shading
import habapp_rules.actors.state_observer
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer


# pylint: disable=protected-access,no-member,too-many-public-methods
class TestShadingBase(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing _ShadingBase."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.RollershutterItem, "Unittest_Shading_min", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual_min", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Shading_max", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual_max", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Shading_min_state", "")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "CustomState", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_WindAlarm", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_SunProtection", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Night", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door", "CLOSED")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Summer", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Hand_Manual_active", "OFF")

		self.shading_min = habapp_rules.actors.shading._ShadingBase("Unittest_Shading_min", "Unittest_Manual_min", habapp_rules.actors.config.shading.CONFIG_DEFAULT)
		self.shading_max = habapp_rules.actors.shading._ShadingBase(
			"Unittest_Shading_max",
			"Unittest_Manual_max",
			habapp_rules.actors.config.shading.CONFIG_DEFAULT,
			[],
			[],
			"Unittest_WindAlarm",
			"Unittest_SunProtection",
			"Unittest_Sleep_state",
			"Unittest_Night",
			"Unittest_Door",
			"Unittest_Summer",
			"Unittest_Hand_Manual_active",
			name_state="CustomState"
		)

	def test__init__(self):
		"""Test __init__."""
		expected_states = [
			{"name": "WindAlarm"},
			{"name": "Manual"},
			{"name": "Hand", "on_timeout": "_auto_hand_timeout", "timeout": 72000},
			{"name": "Auto", "initial": "Init", "children": [
				{"name": "Init"},
				{"name": "Open"},
				{"name": "DoorOpen", "initial": "Open", "children": [
					{"name": "Open"},
					{"name": "PostOpen", "on_timeout": "_timeout_post_door_open", "timeout": 300}
				]},
				{"name": "NightClose"},
				{"name": "SleepingClose"},
				{"name": "SunProtection"}
			]}
		]
		self.assertEqual(expected_states, self.shading_max.states)

		expected_trans = [
			{"trigger": "_wind_alarm_on", "source": ["Auto", "Hand", "Manual"], "dest": "WindAlarm"},
			{"trigger": "_wind_alarm_off", "source": "WindAlarm", "dest": "Manual", "conditions": "_manual_active"},
			{"trigger": "_wind_alarm_off", "source": "WindAlarm", "dest": "Auto", "unless": "_manual_active"},

			# manual
			{"trigger": "_manual_on", "source": ["Auto", "Hand"], "dest": "Manual"},
			{"trigger": "_manual_off", "source": "Manual", "dest": "Auto"},

			# hand
			{"trigger": "_hand_command", "source": ["Auto"], "dest": "Hand"},
			{"trigger": "_auto_hand_timeout", "source": "Hand", "dest": "Auto"},

			# sun
			{"trigger": "_sun_on", "source": "Auto_Open", "dest": "Auto_SunProtection"},
			{"trigger": "_sun_off", "source": "Auto_SunProtection", "dest": "Auto_Open"},

			# sleep
			{"trigger": "_sleep_started", "source": ["Auto_Open", "Auto_NightClose", "Auto_SunProtection"], "dest": "Auto_SleepingClose"},
			{"trigger": "_sleep_started", "source": "Hand", "dest": "Auto"},
			{"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_SunProtection", "conditions": "_sun_protection_active_and_configured"},
			{"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_NightClose", "conditions": ["_night_active_and_configured"]},
			{"trigger": "_sleep_stopped", "source": "Auto_SleepingClose", "dest": "Auto_Open", "unless": ["_night_active_and_configured", "_sun_protection_active_and_configured"]},

			# door
			{"trigger": "_door_open", "source": ["Auto_NightClose", "Auto_SunProtection", "Auto_SleepingClose", "Auto_Open"], "dest": "Auto_DoorOpen"},
			{"trigger": "_door_open", "source": "Auto_DoorOpen_PostOpen", "dest": "Auto_DoorOpen_Open"},
			{"trigger": "_door_closed", "source": "Auto_DoorOpen_Open", "dest": "Auto_DoorOpen_PostOpen"},
			{"trigger": "_timeout_post_door_open", "source": "Auto_DoorOpen_PostOpen", "dest": "Auto_Init"},

			# night close
			{"trigger": "_night_started", "source": ["Auto_Open", "Auto_SunProtection"], "dest": "Auto_NightClose", "conditions": "_night_active_and_configured"},
			{"trigger": "_night_stopped", "source": "Auto_NightClose", "dest": "Auto_SunProtection", "conditions": "_sun_protection_active_and_configured"},
			{"trigger": "_night_stopped", "source": "Auto_NightClose", "dest": "Auto_Open", "unless": ["_sun_protection_active_and_configured"]}
		]

		self.assertEqual(expected_trans, self.shading_max.trans)

		self.assertEqual(5, self.shading_max.state_machine.states["Auto"].states["DoorOpen"].states["PostOpen"].timeout)
		self.assertEqual(86400, self.shading_max.state_machine.states["Manual"].timeout)

	def test_init_exceptions(self):
		"""Test exceptions of __init__."""
		TestCase = collections.namedtuple("TestCase", "item_type, raises_exc")

		test_cases = [
			TestCase(HABApp.openhab.items.RollershutterItem, False),
			TestCase(HABApp.openhab.items.DimmerItem, False),
			TestCase(HABApp.openhab.items.SwitchItem, True),
			TestCase(HABApp.openhab.items.ContactItem, True),
			TestCase(HABApp.openhab.items.NumberItem, True)
		]

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Temp_state", "")

		for test_case in test_cases:
			tests.helper.oh_item.add_mock_item(test_case.item_type, "Unittest_Temp", None)  # NumberItem
			if test_case.raises_exc:
				with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
					habapp_rules.actors.shading._ShadingBase("Unittest_Temp", "Unittest_Manual_min", habapp_rules.actors.config.shading.CONFIG_DEFAULT)
			else:
				habapp_rules.actors.shading._ShadingBase("Unittest_Temp", "Unittest_Manual_min", habapp_rules.actors.config.shading.CONFIG_DEFAULT)
			tests.helper.oh_item.remove_mocked_item_by_name("Unittest_Temp")

	@unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
	def test_create_graph(self):  # pragma: no cover
		"""Create state machine graph for documentation."""
		picture_dir = pathlib.Path(__file__).parent / "Shading_States"
		if not picture_dir.is_dir():
			os.makedirs(picture_dir)

		jal_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
			model=tests.helper.graph_machines.FakeModel(),
			states=self.shading_min.states,
			transitions=self.shading_min.trans,
			initial=self.shading_min.state,
			show_conditions=False)

		jal_graph.get_graph().draw(picture_dir / "Shading.png", format="png", prog="dot")

		for state_name in [state for state in self._get_state_names(self.shading_min.states) if state not in ["auto_init"]]:
			jal_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(
				model=tests.helper.graph_machines.FakeModel(),
				states=self.shading_min.states,
				transitions=self.shading_min.trans,
				initial=state_name,
				show_conditions=True)
			jal_graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Shading_{state_name}.png", format="png", prog="dot")

	def test_check_config(self):
		"""Test _check_config"""
		TestCase = collections.namedtuple("TestCase", "pos_night_close_summer, item_summer, raises_exc")
		self.shading_max._config = copy.deepcopy(habapp_rules.actors.config.shading.CONFIG_DEFAULT)

		test_cases = [
			TestCase(None, None, False),
			TestCase(None, HABApp.openhab.items.SwitchItem("some_name"), False),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(42, 80), None, True),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(42, 80), HABApp.openhab.items.SwitchItem("some_name"), False)
		]

		for test_case in test_cases:
			self.shading_max._config.pos_night_close_summer = test_case.pos_night_close_summer
			self.shading_max._item_summer = test_case.item_summer

			if test_case.raises_exc:
				with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
					self.shading_max._check_config()
			else:
				self.shading_max._check_config()

	@staticmethod
	def get_initial_state_test_cases() -> list[collections.namedtuple]:
		"""Get test cases for initial state tests

		:return: tests cases
		"""
		TestCase = collections.namedtuple("TestCase", "wind_alarm, manual, sleeping_state, door, night, sun_protection, expected_state")

		return [
			# wind_alarm = OFF | manual = OFF
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="OFF", sun_protection="OFF", expected_state="Auto_Open"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="OFF", sun_protection="ON", expected_state="Auto_SunProtection"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="ON", sun_protection="OFF", expected_state="Auto_NightClose"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="ON", sun_protection="ON", expected_state="Auto_NightClose"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="OFF", sun_protection="OFF", expected_state="Auto_DoorOpen_Open"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="OFF", sun_protection="ON", expected_state="Auto_DoorOpen_Open"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="ON", sun_protection="OFF", expected_state="Auto_DoorOpen_Open"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="ON", sun_protection="ON", expected_state="Auto_DoorOpen_Open"),

			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="OFF", sun_protection="OFF", expected_state="Auto_SleepingClose"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="OFF", sun_protection="ON", expected_state="Auto_SleepingClose"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="ON", sun_protection="OFF", expected_state="Auto_SleepingClose"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="ON", sun_protection="ON", expected_state="Auto_SleepingClose"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="OFF", sun_protection="OFF", expected_state="Auto_DoorOpen_Open"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="OFF", sun_protection="ON", expected_state="Auto_DoorOpen_Open"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="ON", sun_protection="OFF", expected_state="Auto_DoorOpen_Open"),
			TestCase(wind_alarm="OFF", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="ON", sun_protection="ON", expected_state="Auto_DoorOpen_Open"),

			# wind_alarm = OFF | manual = ON
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="OFF", sun_protection="OFF", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="OFF", sun_protection="ON", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="ON", sun_protection="OFF", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="ON", sun_protection="ON", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="OFF", sun_protection="OFF", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="OFF", sun_protection="ON", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="ON", sun_protection="OFF", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="ON", sun_protection="ON", expected_state="Manual"),

			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="OFF", sun_protection="OFF", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="OFF", sun_protection="ON", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="ON", sun_protection="OFF", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="ON", sun_protection="ON", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="OFF", sun_protection="OFF", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="OFF", sun_protection="ON", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="ON", sun_protection="OFF", expected_state="Manual"),
			TestCase(wind_alarm="OFF", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="ON", sun_protection="ON", expected_state="Manual"),

			# wind_alarm = ON | manual = OFF
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="OFF", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="OFF", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="ON", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="ON", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="OFF", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="OFF", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="ON", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="ON", sun_protection="ON", expected_state="WindAlarm"),

			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="OFF", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="OFF", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="ON", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="ON", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="OFF", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="OFF", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="ON", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="OFF", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="ON", sun_protection="ON", expected_state="WindAlarm"),

			# wind_alarm = ON | manual = ON
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="OFF", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="OFF", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="ON", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="CLOSED", night="ON", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="OFF", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="OFF", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="ON", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.AWAKE, door="OPEN", night="ON", sun_protection="ON", expected_state="WindAlarm"),

			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="OFF", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="OFF", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="ON", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="CLOSED", night="ON", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="OFF", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="OFF", sun_protection="ON", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="ON", sun_protection="OFF", expected_state="WindAlarm"),
			TestCase(wind_alarm="ON", manual="ON", sleeping_state=habapp_rules.system.SleepState.SLEEPING, door="OPEN", night="ON", sun_protection="ON", expected_state="WindAlarm"),
		]

	def test_get_initial_state(self):
		"""Test _get_initial_state."""
		for test_case in self.get_initial_state_test_cases():
			tests.helper.oh_item.set_state("Unittest_WindAlarm", test_case.wind_alarm)
			tests.helper.oh_item.set_state("Unittest_Manual_max", test_case.manual)
			tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleeping_state.value)
			tests.helper.oh_item.set_state("Unittest_Door", test_case.door)
			tests.helper.oh_item.set_state("Unittest_Night", test_case.night)
			tests.helper.oh_item.set_state("Unittest_SunProtection", test_case.sun_protection)

			self.assertEqual(test_case.expected_state, self.shading_max._get_initial_state())

	@staticmethod
	def get_target_positions_test_cases() -> list[collections.namedtuple]:
		"""Get test cases for target position

		:return: tests cases
		"""
		TestCase = collections.namedtuple("TestCase", "state, target_pos")

		return [
			TestCase("Hand", None),
			TestCase("Manual", None),
			TestCase("WindAlarm", habapp_rules.actors.config.shading.ShadingPosition(0, 0)),
			TestCase("Auto_Open", habapp_rules.actors.config.shading.ShadingPosition(0, 0)),
			TestCase("Auto_SunProtection", habapp_rules.actors.config.shading.ShadingPosition(100, None)),
			TestCase("Auto_SleepingClose", habapp_rules.actors.config.shading.ShadingPosition(100, 100)),
			TestCase("Auto_NightClose", habapp_rules.actors.config.shading.ShadingPosition(100, 100)),
			TestCase("Auto_DoorOpen_Open", habapp_rules.actors.config.shading.ShadingPosition(0, 0)),
			TestCase("Auto_DoorOpen_PostOpen", None),
		]

	def test_get_target_position(self):
		"""Test _get_target_position."""
		for test_case in self.get_target_positions_test_cases():
			self.shading_max._set_state(test_case.state)
			self.assertEqual(test_case.target_pos, self.shading_max._get_target_position())

		tests.helper.oh_item.send_command("Unittest_Summer", "ON", "OFF")
		self.shading_max._set_state("Auto_NightClose")
		self.assertEqual(None, self.shading_max._get_target_position())

	def test_cb_sleep_state(self):
		"""Test _cb_sleep_state"""
		TestCase = collections.namedtuple("TestCase", "sleep_state, started_triggered, stopped_triggered")

		test_cases = [
			TestCase(habapp_rules.system.SleepState.AWAKE, False, False),
			TestCase(habapp_rules.system.SleepState.PRE_SLEEPING, True, False),
			TestCase(habapp_rules.system.SleepState.SLEEPING, False, False),
			TestCase(habapp_rules.system.SleepState.POST_SLEEPING, False, True),
			TestCase(habapp_rules.system.SleepState.LOCKED, False, False),
		]

		with unittest.mock.patch.object(self.shading_max, "_sleep_started") as started_mock, unittest.mock.patch.object(self.shading_max, "_sleep_stopped") as stopped_mock:
			for test_case in test_cases:
				started_mock.reset_mock()
				stopped_mock.reset_mock()

				tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", test_case.sleep_state.value)

				if test_case.started_triggered:
					started_mock.assert_called_once()
				else:
					started_mock.assert_not_called()

				if test_case.stopped_triggered:
					stopped_mock.assert_called_once()
				else:
					stopped_mock.assert_not_called()

	def test_cb_hand(self):
		"""Test _cb_hand."""
		self.shading_min.to_Auto()
		self.shading_max.to_Auto()

		self.shading_min._cb_hand(unittest.mock.MagicMock())
		self.shading_max._cb_hand(unittest.mock.MagicMock())

		self.assertEqual("Hand", self.shading_min.state)
		self.assertEqual("Hand", self.shading_max.state)

	def test_night_active_and_configured(self):
		"""Test _night_active_and_configured."""
		TestCase = collections.namedtuple("TestCase", "night, summer, config_summer, config_winter, expected_result")

		shading_pos = habapp_rules.actors.config.shading.ShadingPosition(42, 0)

		test_cases = [
			# night off
			TestCase("OFF", None, None, None, False),
			TestCase("OFF", None, None, shading_pos, False),
			TestCase("OFF", None, shading_pos, None, False),
			TestCase("OFF", None, shading_pos, shading_pos, False),

			TestCase("OFF", "OFF", None, None, False),
			TestCase("OFF", "OFF", None, shading_pos, False),
			TestCase("OFF", "OFF", shading_pos, None, False),
			TestCase("OFF", "OFF", shading_pos, shading_pos, False),

			TestCase("OFF", "ON", None, None, False),
			TestCase("OFF", "ON", None, shading_pos, False),
			TestCase("OFF", "ON", shading_pos, None, False),
			TestCase("OFF", "ON", shading_pos, shading_pos, False),

			# night on
			TestCase("ON", None, None, None, False),
			TestCase("ON", None, None, shading_pos, True),
			TestCase("ON", None, shading_pos, None, False),
			TestCase("ON", None, shading_pos, shading_pos, True),

			TestCase("ON", "OFF", None, None, False),
			TestCase("ON", "OFF", None, shading_pos, True),
			TestCase("ON", "OFF", shading_pos, None, False),
			TestCase("ON", "OFF", shading_pos, shading_pos, True),

			TestCase("ON", "ON", None, None, False),
			TestCase("ON", "ON", None, shading_pos, False),
			TestCase("ON", "ON", shading_pos, None, True),
			TestCase("ON", "ON", shading_pos, shading_pos, True),
		]

		for test_case in test_cases:
			with unittest.mock.patch.object(self.shading_max._config, "pos_night_close_summer", test_case.config_summer), unittest.mock.patch.object(self.shading_max._config, "pos_night_close_winter", test_case.config_winter):
				tests.helper.oh_item.set_state("Unittest_Summer", test_case.summer)
				tests.helper.oh_item.set_state("Unittest_Night", test_case.night)

				self.assertEqual(test_case.expected_result, self.shading_max._night_active_and_configured())

	def test_manual_transitions(self):
		"""Test transitions of state manual"""

		for initial_state in ("Hand", "Auto"):
			self.shading_min.state_machine.set_state(initial_state)
			self.shading_max.state_machine.set_state(initial_state)
			tests.helper.oh_item.item_state_change_event("Unittest_Manual_min", "ON", "OFF")
			tests.helper.oh_item.item_state_change_event("Unittest_Manual_max", "ON", "OFF")
			self.assertEqual("Manual", self.shading_min.state)
			self.assertEqual("Manual", self.shading_max.state)

		# to WindAlarm | without wind_alarm_item
		self.shading_min.to_Manual()
		tests.helper.oh_item.send_command("Unittest_WindAlarm", "ON", "OFF")
		self.assertEqual("Manual", self.shading_min.state)

		# to WindAlarm | with wind_alarm_item (and back to manual -> states must be the same as before)
		self.shading_max.to_Manual()
		tests.helper.oh_item.send_command("Unittest_WindAlarm", "ON", "OFF")
		self.assertEqual("WindAlarm", self.shading_max.state)

		# to Auto (manual off)
		self.shading_min.to_Manual()
		self.shading_max.to_Manual()
		tests.helper.oh_item.send_command("Unittest_WindAlarm", "OFF", "ON")
		tests.helper.oh_item.send_command("Unittest_Manual_min", "OFF", "ON")
		tests.helper.oh_item.send_command("Unittest_Manual_max", "OFF", "ON")
		self.assertEqual("Auto_Open", self.shading_min.state)
		self.assertEqual("Auto_Open", self.shading_max.state)

	def test_hand_transitions(self):
		"""Test transitions of state hand"""
		# from auto to hand
		self.shading_min.to_Auto()
		self.shading_max.to_Auto()
		self.shading_min._hand_command()
		self.shading_max._hand_command()
		self.assertEqual("Hand", self.shading_min.state)
		self.assertEqual("Hand", self.shading_max.state)

		# from hand to auto
		self.shading_min.to_Hand()
		self.shading_max.to_Hand()
		self.shading_min._auto_hand_timeout()
		self.shading_max._auto_hand_timeout()
		self.assertEqual("Auto_Open", self.shading_min.state)
		self.assertEqual("Auto_Open", self.shading_max.state)

		# from hand to manual
		self.shading_min.to_Hand()
		self.shading_max.to_Hand()
		tests.helper.oh_item.send_command("Unittest_Manual_min", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Manual_max", "ON", "OFF")
		self.assertEqual("Manual", self.shading_min.state)
		self.assertEqual("Manual", self.shading_max.state)

		# from hand to wind_alarm
		self.shading_min.to_Hand()
		self.shading_max.to_Hand()
		tests.helper.oh_item.send_command("Unittest_WindAlarm", "ON", "OFF")
		self.assertEqual("Hand", self.shading_min.state)
		self.assertEqual("WindAlarm", self.shading_max.state)

	def test_wind_alarm_transitions(self):
		"""Test transitions of state WindAlarm"""
		# from wind_alarm to manual
		self.shading_max.to_WindAlarm()
		tests.helper.oh_item.send_command("Unittest_Manual_max", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_WindAlarm", "OFF", "ON")
		self.assertEqual("Manual", self.shading_max.state)

		# from wind_alarm to Auto
		self.shading_max.to_WindAlarm()
		tests.helper.oh_item.send_command("Unittest_Manual_max", "OFF", "ON")
		tests.helper.oh_item.send_command("Unittest_WindAlarm", "OFF", "ON")
		self.assertEqual("Auto_Open", self.shading_max.state)

	def test_auto_open_transitions(self):
		"""Test transitions of state Auto_Open"""
		# to door_open
		self.shading_min.to_Auto_Open()
		self.shading_max.to_Auto_Open()
		tests.helper.oh_item.send_command("Unittest_Door", "OPEN", "CLOSED")
		self.assertEqual("Auto_Open", self.shading_min.state)
		self.assertEqual("Auto_DoorOpen_Open", self.shading_max.state)

		# to night_close | configured
		self.shading_min.to_Auto_Open()
		self.shading_max.to_Auto_Open()
		tests.helper.oh_item.send_command("Unittest_Night", "ON", "OFF")
		self.assertEqual("Auto_Open", self.shading_min.state)
		self.assertEqual("Auto_NightClose", self.shading_max.state)

		# to night_close | NOT configured
		self.shading_min.to_Auto_Open()
		self.shading_max.to_Auto_Open()
		tests.helper.oh_item.send_command("Unittest_Summer", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Night", "ON", "OFF")
		self.assertEqual("Auto_Open", self.shading_min.state)
		self.assertEqual("Auto_Open", self.shading_max.state)

		# to sleeping_close
		self.shading_min.to_Auto_Open()
		self.shading_max.to_Auto_Open()
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("Auto_Open", self.shading_min.state)
		self.assertEqual("Auto_SleepingClose", self.shading_max.state)

		# to sun_protection
		self.shading_min.to_Auto_Open()
		self.shading_max.to_Auto_Open()
		tests.helper.oh_item.send_command("Unittest_SunProtection", "ON", "OFF")
		self.assertEqual("Auto_Open", self.shading_min.state)
		self.assertEqual("Auto_SunProtection", self.shading_max.state)

	def test_auto_night_close_transitions(self):
		"""Test transitions of state Auto_NightClose"""
		# to open
		self.shading_max.to_Auto_NightClose()
		tests.helper.oh_item.send_command("Unittest_SunProtection", "OFF", "ON")
		tests.helper.oh_item.send_command("Unittest_Night", "OFF", "ON")
		self.assertEqual("Auto_Open", self.shading_max.state)

		# to door_open
		self.shading_max.to_Auto_NightClose()
		tests.helper.oh_item.send_command("Unittest_Door", "OPEN", "CLOSED")
		self.assertEqual("Auto_DoorOpen_Open", self.shading_max.state)

		# to sleeping_close
		self.shading_max.to_Auto_NightClose()
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("Auto_SleepingClose", self.shading_max.state)

		# to sun_protection
		self.shading_max.to_Auto_NightClose()
		tests.helper.oh_item.send_command("Unittest_SunProtection", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Night", "OFF", "ON")
		self.assertEqual("Auto_SunProtection", self.shading_max.state)

	def test_auto_sleeping_close_transitions(self):
		"""Test transitions of state Auto_SleepingClose"""
		# to open
		self.shading_max.to_Auto_SleepingClose()
		tests.helper.oh_item.send_command("Unittest_Night", "OFF", "ON")
		tests.helper.oh_item.send_command("Unittest_SunProtection", "OFF", "OFF")
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)
		self.assertEqual("Auto_Open", self.shading_max.state)

		# to night_close | configured
		self.shading_max.to_Auto_SleepingClose()
		tests.helper.oh_item.send_command("Unittest_Night", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)
		self.assertEqual("Auto_NightClose", self.shading_max.state)

		# to night_close | NOT configured
		self.shading_max.to_Auto_SleepingClose()
		tests.helper.oh_item.send_command("Unittest_Summer", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Night", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)
		self.assertEqual("Auto_Open", self.shading_max.state)

		# to door_open
		self.shading_max.to_Auto_SleepingClose()
		tests.helper.oh_item.send_command("Unittest_Door", "OPEN", "CLOSED")
		self.assertEqual("Auto_DoorOpen_Open", self.shading_max.state)

		# to sun_protection
		self.shading_max.to_Auto_SleepingClose()
		tests.helper.oh_item.send_command("Unittest_SunProtection", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.SleepState.SLEEPING.value)
		self.assertEqual("Auto_SunProtection", self.shading_max.state)

	def test_auto_sun_protection_transitions(self):
		"""Test transitions of state Auto_SunProtection"""
		# to open
		self.shading_max.to_Auto_SunProtection()
		tests.helper.oh_item.send_command("Unittest_SunProtection", "OFF", "ON")
		self.assertEqual("Auto_Open", self.shading_max.state)

		# to night_close | configured
		self.shading_max.to_Auto_SunProtection()
		tests.helper.oh_item.send_command("Unittest_Night", "ON", "OFF")
		self.assertEqual("Auto_NightClose", self.shading_max.state)

		# to night_close | NOT configured
		self.shading_max.to_Auto_SunProtection()
		tests.helper.oh_item.send_command("Unittest_Summer", "ON", "OFF")
		tests.helper.oh_item.send_command("Unittest_Night", "ON", "OFF")
		self.assertEqual("Auto_SunProtection", self.shading_max.state)

		# to sleeping_protection
		self.shading_max.to_Auto_SunProtection()
		tests.helper.oh_item.send_command("Unittest_Sleep_state", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.SleepState.AWAKE.value)
		self.assertEqual("Auto_SleepingClose", self.shading_max.state)

		# to door_open
		self.shading_max.to_Auto_SunProtection()
		tests.helper.oh_item.send_command("Unittest_Door", "OPEN", "CLOSED")
		self.assertEqual("Auto_DoorOpen_Open", self.shading_max.state)

	def test_auto_door_open_transitions(self):
		"""Test transitions of state Auto_DoorOpen"""
		# door closed -> PostOpen
		self.shading_max.to_Auto_DoorOpen_Open()
		tests.helper.oh_item.send_command("Unittest_Door", "CLOSED", "OPEN")
		self.assertEqual("Auto_DoorOpen_PostOpen", self.shading_max.state)

		# door opened again -> Open
		tests.helper.oh_item.send_command("Unittest_Door", "OPEN", "CLOSED")
		self.assertEqual("Auto_DoorOpen_Open", self.shading_max.state)

		# door closed + timeout -> AutoInit
		tests.helper.oh_item.send_command("Unittest_Door", "CLOSED", "OPEN")
		self.shading_max._timeout_post_door_open()
		self.assertEqual("Auto_Open", self.shading_max.state)


class TestShadingShutter(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing Raffstore class."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Shading", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Shading_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_WindAlarm", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_SunProtection", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Night", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door", "CLOSED")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Summer", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Hand_Manual_active", "OFF")

		self.shutter = habapp_rules.actors.shading.Shutter(
			"Unittest_Shading",
			"Unittest_Manual",
			habapp_rules.actors.config.shading.CONFIG_DEFAULT,
			[],
			[],
			"Unittest_WindAlarm",
			"Unittest_SunProtection",
			"Unittest_Sleep_state",
			"Unittest_Night",
			"Unittest_Door",
			"Unittest_Summer",
			"Unittest_Hand_Manual_active"
		)

	def test_set_shading_state(self):
		"""Test _set_shading_state."""
		TestCase = collections.namedtuple("TestCase", "target_pos, sent_pos")

		test_cases = [
			TestCase(None, None),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(None, None), None),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(None, 25), None),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(50, None), 50),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(80, 90), 80),

			TestCase(habapp_rules.actors.config.shading.ShadingPosition(0, 0), 0),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(0, 25), 0),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(50, 0), 50),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(80, 90), 80),
		]

		with unittest.mock.patch.object(self.shutter, "_get_target_position") as get_pos_mock, unittest.mock.patch.object(self.shutter._state_observer_pos, "send_command") as send_pos_mock:
			for test_case in test_cases:
				get_pos_mock.return_value = test_case.target_pos
				send_pos_mock.reset_mock()

				self.shutter._set_shading_state()

				if test_case.sent_pos is None:
					send_pos_mock.assert_not_called()
				else:
					send_pos_mock.assert_called_once_with(test_case.sent_pos)


class TestShadingRaffstore(tests.helper.test_case_base.TestCaseBase):
	"""Tests cases for testing Raffstore class."""

	def setUp(self) -> None:
		"""Setup test case."""
		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
		self.addCleanup(self.transitions_timer_mock_patcher.stop)
		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()

		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
		self.addCleanup(self.threading_timer_mock_patcher.stop)
		self.threading_timer_mock = self.threading_timer_mock_patcher.start()

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.RollershutterItem, "Unittest_Shading", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Slat", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", "OFF")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Shading_state", "")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_WindAlarm", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_SunProtection", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_SunProtection_Slat", 83)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Night", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door", "CLOSED")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Summer", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Hand_Manual_active", "OFF")

		self.raffstore = habapp_rules.actors.shading.Raffstore(
			"Unittest_Shading",
			"Unittest_Slat",
			"Unittest_Manual",
			habapp_rules.actors.config.shading.CONFIG_DEFAULT,
			[],
			[],
			"Unittest_WindAlarm",
			"Unittest_SunProtection",
			"Unittest_SunProtection_Slat",
			"Unittest_Sleep_state",
			"Unittest_Night",
			"Unittest_Door",
			"Unittest_Summer",
			"Unittest_Hand_Manual_active"
		)

	def test_init(self):
		"""Test __init__"""
		self.assertEqual("Unittest_Slat", self.raffstore._item_slat.name)
		self.assertEqual("Unittest_SunProtection_Slat", self.raffstore._item_sun_protection_slat.name)

	def test_init_min(self):
		"""Test init of raffstore with minimal attributes."""
		habapp_rules.actors.shading.Raffstore(
			"Unittest_Shading",
			"Unittest_Slat",
			"Unittest_Manual",
			habapp_rules.actors.config.shading.CONFIG_DEFAULT,
		)

	def test_verify_items(self):
		"""Test __verify_items"""
		# test shading position type
		TestCase = collections.namedtuple("TestCase", "item_type, raises_exc")

		test_cases = [
			TestCase(HABApp.openhab.items.RollershutterItem, False),
			TestCase(HABApp.openhab.items.DimmerItem, True),
			TestCase(HABApp.openhab.items.SwitchItem, True),
			TestCase(HABApp.openhab.items.ContactItem, True),
			TestCase(HABApp.openhab.items.NumberItem, True)
		]

		for test_case in test_cases:
			self.raffstore._item_shading_position = test_case.item_type("Name")
			if test_case.raises_exc:
				with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
					self.raffstore._Raffstore__verify_items()
			else:
				self.raffstore._Raffstore__verify_items()

		# test sun protection items
		TestCase = collections.namedtuple("TestCase", "item_sun_protection, item_sun_protection_slat, raises_exc")
		test_cases = [
			TestCase(None, None, False),
			TestCase(None, HABApp.openhab.items.DimmerItem("slat"), True),
			TestCase(HABApp.openhab.items.DimmerItem("sun_protection"), None, True),
			TestCase(HABApp.openhab.items.DimmerItem("sun_protection"), HABApp.openhab.items.DimmerItem("slat"), False)
		]
		self.raffstore._item_shading_position = HABApp.openhab.items.RollershutterItem("Name")

		for test_case in test_cases:
			self.raffstore._item_sun_protection = test_case.item_sun_protection
			self.raffstore._item_sun_protection_slat = test_case.item_sun_protection_slat
			if test_case.raises_exc:
				with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
					self.raffstore._Raffstore__verify_items()
			else:
				self.raffstore._Raffstore__verify_items()

	def test_get_target_position(self):
		"""Test _get_target_position."""
		TestCase = collections.namedtuple("TestCase", "state, target_pos")

		test_cases = TestShadingBase.get_target_positions_test_cases()
		test_cases[4] = TestCase("Auto_SunProtection", habapp_rules.actors.config.shading.ShadingPosition(100, 83))

		for test_case in test_cases:
			self.raffstore._set_state(test_case.state)
			self.assertEqual(test_case.target_pos, self.raffstore._get_target_position())

	def test_set_shading_state(self):
		"""Test _set_shading_state"""
		TestCase = collections.namedtuple("TestCase", "target_pos, sent_pos, sent_slat")

		test_cases = [
			TestCase(None, None, None),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(None, None), None, None),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(None, 25), None, 25),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(50, None), 50, None),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(80, 90), 80, 90),

			TestCase(habapp_rules.actors.config.shading.ShadingPosition(0, 0), 0, 0),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(0, 25), 0, 25),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(50, 0), 50, 0),
			TestCase(habapp_rules.actors.config.shading.ShadingPosition(80, 90), 80, 90),
		]

		with (unittest.mock.patch.object(self.raffstore, "_get_target_position") as get_pos_mock,
		      unittest.mock.patch.object(self.raffstore._state_observer_pos, "send_command") as send_pos_mock,
		      unittest.mock.patch.object(self.raffstore._state_observer_slat, "send_command") as send_slat_mock):
			for test_case in test_cases:
				get_pos_mock.return_value = test_case.target_pos
				send_pos_mock.reset_mock()
				send_slat_mock.reset_mock()

				self.raffstore._set_shading_state()

				if test_case.sent_pos is None:
					send_pos_mock.assert_not_called()
				else:
					send_pos_mock.assert_called_once_with(test_case.sent_pos)

				if test_case.sent_slat is None:
					send_slat_mock.assert_not_called()
				else:
					send_slat_mock.assert_called_once_with(test_case.sent_slat)

	def test_cb_slat(self):
		"""Test _cb_slat"""
		with unittest.mock.patch.object(self.raffstore._state_observer_slat, "send_command") as send_command_mock:
			tests.helper.oh_item.send_command("Unittest_Manual", "ON", "OFF")
			tests.helper.oh_item.send_command("Unittest_SunProtection_Slat", 15, 99)
			send_command_mock.assert_not_called()

			tests.helper.oh_item.send_command("Unittest_Manual", "OFF", "ON")
			tests.helper.oh_item.send_command("Unittest_SunProtection", "ON", "OFF")
			self.assertEqual("Auto_SunProtection", self.raffstore.state)
			tests.helper.oh_item.send_command("Unittest_SunProtection_Slat", 22, 15)
			send_command_mock.assert_has_calls([
				unittest.mock.call(0),
				unittest.mock.call(15),
				unittest.mock.call(22)
			])

	def test_manual_position_restore(self):
		"""Test if manual position is restored correctly"""
		tests.helper.oh_item.send_command("Unittest_Manual", "ON", "OFF")

		tests.helper.oh_item.send_command("Unittest_Shading", 12)
		tests.helper.oh_item.send_command("Unittest_Slat", 34)

		tests.helper.oh_item.send_command("Unittest_WindAlarm", "ON", "OFF")
		tests.helper.oh_item.assert_value("Unittest_Shading", 0)
		tests.helper.oh_item.assert_value("Unittest_Slat", 0)

		tests.helper.oh_item.send_command("Unittest_WindAlarm", "OFF", "ON")
		tests.helper.oh_item.assert_value("Unittest_Shading", 12)
		tests.helper.oh_item.assert_value("Unittest_Slat", 34)


class TestResetAllManualHand(tests.helper.test_case_base.TestCaseBase):
	"""Tests for ResetAllManualHand"""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Reset", None)

		self.reset_shading_rule = habapp_rules.actors.shading.ResetAllManualHand("Unittest_Reset")

	def test__get_shading_objects(self):
		"""Test __get_shading_objects."""
		with unittest.mock.patch.object(self.reset_shading_rule, "get_rule") as get_rule_mock:
			self.reset_shading_rule._ResetAllManualHand__get_shading_objects()

		get_rule_mock.assert_called_once_with(None)

	def test_cb_reset_all(self):
		"""Test _cb_reset_all."""
		TestCase = collections.namedtuple("TestCase", "event, state, manual_commands")

		test_cases = [
			TestCase("OFF", "Auto", []),
			TestCase("OFF", "Hand", []),
			TestCase("OFF", "Manual", []),

			TestCase("ON", "Auto", []),
			TestCase("ON", "Hand", [unittest.mock.call("ON"), unittest.mock.call("OFF")]),
			TestCase("ON", "Manual", [unittest.mock.call("OFF")])
		]

		shading_rule_mock = unittest.mock.MagicMock(spec=habapp_rules.actors.shading.Raffstore)
		shading_rule_mock._item_manual = unittest.mock.MagicMock(spec=HABApp.openhab.items.SwitchItem)

		with unittest.mock.patch.object(self.reset_shading_rule, "_ResetAllManualHand__get_shading_objects", return_value=[shading_rule_mock]):
			for test_case in test_cases:
				shading_rule_mock.state = test_case.state
				shading_rule_mock._item_manual.oh_send_command.reset_mock()

				self.reset_shading_rule._cb_reset_all(HABApp.openhab.events.ItemCommandEvent("name", test_case.event))

				self.assertEqual(len(test_case.manual_commands), shading_rule_mock._item_manual.oh_send_command.call_count)
				shading_rule_mock._item_manual.oh_send_command.assert_has_calls(test_case.manual_commands)


class TestSlatValueSun(tests.helper.test_case_base.TestCaseBase):
	"""Tests for SlatValueSun."""

	def setUp(self):
		"""Setup test case."""

		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Elevation", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Summer", "ON")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_SlatValueSingle", 0)  # NumberItem
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_SlatValueDual", 0)  # DimmerItem

		self.characteristic_winter = [(0, 100), (10, 70), (20, 60), (30, 50), (40, 50)]
		self.characteristic_summer = [(0, 100), (10, 80), (20, 70), (30, 60), (40, 50), (50, 50)]

		self.slat_value_sun_single = habapp_rules.actors.shading.SlatValueSun("Unittest_Elevation", "Unittest_SlatValueSingle", self.characteristic_winter)
		self.slat_value_sun_dual = habapp_rules.actors.shading.SlatValueSun("Unittest_Elevation", "Unittest_SlatValueDual", self.characteristic_winter, "Unittest_Summer", self.characteristic_summer)

	def test_init(self):
		"""Test __init__."""
		# single
		self.assertEqual("Unittest_Elevation", self.slat_value_sun_single._item_sun_elevation.name)
		self.assertEqual(self.characteristic_winter, self.slat_value_sun_single._SlatValueSun__slat_characteristic_default)
		self.assertEqual(None, self.slat_value_sun_single._SlatValueSun__slat_characteristic_summer)
		self.assertEqual("Unittest_SlatValueSingle", self.slat_value_sun_single._item_slat_value.name)
		self.assertEqual(None, self.slat_value_sun_single._item_summer)
		self.assertEqual(self.characteristic_winter, self.slat_value_sun_single._slat_characteristic_active)

		# with summer / winter
		self.assertEqual("Unittest_Elevation", self.slat_value_sun_dual._item_sun_elevation.name)
		self.assertEqual(self.characteristic_winter, self.slat_value_sun_dual._SlatValueSun__slat_characteristic_default)
		self.assertEqual(self.characteristic_summer, self.slat_value_sun_dual._SlatValueSun__slat_characteristic_summer)
		self.assertEqual("Unittest_SlatValueDual", self.slat_value_sun_dual._item_slat_value.name)
		self.assertEqual("Unittest_Summer", self.slat_value_sun_dual._item_summer.name)
		self.assertEqual(self.characteristic_summer, self.slat_value_sun_dual._slat_characteristic_active)

	def test_init_exception(self):
		"""Test exceptions of __init__."""
		# summer_name is given but no summer_characteristic
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.actors.shading.SlatValueSun("Unittest_Elevation", "Unittest_SlatValueDual", self.characteristic_winter, "Unittest_Summer")

		# summer_characteristic but no summer_name
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.actors.shading.SlatValueSun("Unittest_Elevation", "Unittest_SlatValueDual", self.characteristic_winter, None, self.characteristic_summer)

		# exception if a wrong type is given for name_slat_value
		TestCase = collections.namedtuple("TestCase", "slat_type, raises_exc")
		test_cases = [
			TestCase(HABApp.openhab.items.RollershutterItem, True),
			TestCase(HABApp.openhab.items.DimmerItem, False),
			TestCase(HABApp.openhab.items.SwitchItem, True),
			TestCase(HABApp.openhab.items.ContactItem, True),
			TestCase(HABApp.openhab.items.NumberItem, False)
		]

		for test_case in test_cases:
			tests.helper.oh_item.add_mock_item(test_case.slat_type, "Unittest_SlatValueTypeTest", None)  # NumberItem
			if test_case.raises_exc:
				with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
					habapp_rules.actors.shading.SlatValueSun("Unittest_Elevation", "Unittest_SlatValueTypeTest", self.characteristic_winter)
			else:
				habapp_rules.actors.shading.SlatValueSun("Unittest_Elevation", "Unittest_SlatValueTypeTest", self.characteristic_winter)
			tests.helper.oh_item.remove_mocked_item_by_name("Unittest_SlatValueTypeTest")

	def test__check_and_sort_characteristic(self):
		"""Test __check_and_sort_characteristic."""
		TestCase = collections.namedtuple("TestCase", "input, expected_output, raises")

		test_cases = [
			TestCase([(0, 100), (10, 50)], [(0, 100), (10, 50)], False),
			TestCase([(10, 50), (0, 100)], [(0, 100), (10, 50)], False),

			TestCase([(0, 100), (10, 50), (20, 50)], [(0, 100), (10, 50), (20, 50)], False),
			TestCase([(10, 50), (0, 100), (20, 50)], [(0, 100), (10, 50), (20, 50)], False),
			TestCase([(10, 50), (20, 50), (0, 100)], [(0, 100), (10, 50), (20, 50)], False),

			TestCase(None, None, True),
			TestCase([(1, 2, 3)], None, True),
			TestCase([1, 2, 3], None, True),
			TestCase([(0, 50), (1)], None, True),
			TestCase([(0, 50), (0)], None, True),
			TestCase([(0, 50), (1, 2, 3)], None, True),
			TestCase([(0, 50), (0, 40)], None, True),
			TestCase([(0, 50), (10, 40), (0, 100)], None, True),
		]

		for test_case in test_cases:
			if test_case.raises:
				with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
					self.slat_value_sun_single._SlatValueSun__check_and_sort_characteristic(test_case.input)
			else:
				self.assertEqual(test_case.expected_output, self.slat_value_sun_single._SlatValueSun__check_and_sort_characteristic(test_case.input))

	def test__get_slat_value(self):
		"""Test __get_slat_value."""
		TestCase = collections.namedtuple("TestCase", "elevation, expected_result_single, , expected_result_dual")

		test_cases = [
			TestCase(-10, 100, 100),

			TestCase(-1, 100, 100),
			TestCase(0, 100, 100),
			TestCase(1, 100, 100),

			TestCase(9, 100, 100),
			TestCase(10, 70, 80),
			TestCase(11, 70, 80),

			TestCase(29, 60, 70),
			TestCase(30, 50, 60),
			TestCase(31, 50, 60),

			TestCase(39, 50, 60),
			TestCase(40, 50, 50),
			TestCase(41, 50, 50),

			TestCase(60, 50, 50),
		]

		for test_case in test_cases:
			self.assertEqual(test_case.expected_result_single, self.slat_value_sun_single._SlatValueSun__get_slat_value(test_case.elevation))
			self.assertEqual(test_case.expected_result_dual, self.slat_value_sun_dual._SlatValueSun__get_slat_value(test_case.elevation))

	def test_cb_elevation(self):
		"""Test _cb_elevation."""
		with unittest.mock.patch.object(self.slat_value_sun_single, "_SlatValueSun__get_slat_value", return_value=42):
			tests.helper.oh_item.assert_value("Unittest_SlatValueSingle", 0)
			tests.helper.oh_item.item_state_change_event("Unittest_Elevation", 10)
			tests.helper.oh_item.assert_value("Unittest_SlatValueSingle", 42)

			tests.helper.oh_item.item_state_change_event("Unittest_Elevation", 11)
			tests.helper.oh_item.assert_value("Unittest_SlatValueSingle", 42)

	def test_cb_summer_winter(self):
		"""Test _cb_summer_winter."""
		# initial -> summer
		tests.helper.oh_item.item_state_change_event("Unittest_Elevation", 30)
		self.assertEqual(self.characteristic_summer, self.slat_value_sun_dual._slat_characteristic_active)
		tests.helper.oh_item.assert_value("Unittest_SlatValueDual", 60)

		# change to winter
		tests.helper.oh_item.item_state_change_event("Unittest_Summer", "OFF")
		self.assertEqual(self.characteristic_winter, self.slat_value_sun_dual._slat_characteristic_active)
		tests.helper.oh_item.assert_value("Unittest_SlatValueDual", 50)

		# change to summer
		tests.helper.oh_item.item_state_change_event("Unittest_Summer", "ON")
		self.assertEqual(self.characteristic_summer, self.slat_value_sun_dual._slat_characteristic_active)
		tests.helper.oh_item.assert_value("Unittest_SlatValueDual", 60)
