"""Test Light rule."""
import collections
import pathlib
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import habapp_rules.system
import habapp_rules.actors.light
import habapp_rules.common.state_machine_rule
import tests.common.graph_machines
import tests.helper.oh_item
import tests.helper.rule_runner
import tests.helper.timer


# pylint: disable=protected-access
class TestLight(unittest.TestCase):
	"""Tests cases for testing Light rule."""

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

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light_ctr", 0)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", True)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state", habapp_rules.system.PresenceState.PRESENCE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state", habapp_rules.system.SleepState.AWAKE.value)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_Light_state", "")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Day", True)

		light_config = habapp_rules.actors.light.LightConfig(
			on=habapp_rules.actors.light.StateConfig(True, 80, 40, 5, 5, 5),
			pre_off=habapp_rules.actors.light.StateConfig(40, 40, 0, 4, 4, 0),
			leaving=habapp_rules.actors.light.StateConfig(False, 40, 0, 0, 10, 0),
			pre_sleep=habapp_rules.actors.light.StateConfig(0, 10, 0, 0, 20, 0)
		)
		with unittest.mock.patch.object(habapp_rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			self._light = habapp_rules.actors.light.Light("Unittest_Light", ["Unittest_Light_ctr"], "Unittest_Manual", "Unittest_Presence_state", "Unittest_Sleep_state", "Unittest_Day", light_config)

	def test_create_graph(self):
		"""Create state machine graph for documentation."""
		presence_graph = tests.common.graph_machines.HierarchicalGraphMachineTimer(
			model=self._light,
			states=self._light.states,
			transitions=self._light.trans,
			initial=self._light.state,
			show_conditions=True)

		presence_graph.get_graph().draw(pathlib.Path(__file__).parent / "Light.png", format="png", prog="dot")

	def test_get_initial_state(self):
		"""Test if correct initial state will be set."""
		TestCase = collections.namedtuple("TestCase", "light_value, manual_value, sleep_value, presence_value, expected_state")
		test_cases = [
			# state OFF + Manual OFF
			TestCase(0, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			TestCase(0, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			TestCase(0, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			TestCase(0, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			TestCase(0, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_off"),
			TestCase(0, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_off"),

			# state OFF + Manual ON
			TestCase(0, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(0, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(0, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(0, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(0, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(0, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			# state ON + Manual OFF
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			TestCase(42, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_presleep"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_presleep"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			TestCase(42, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_presleep"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_presleep"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "auto_on"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LEAVING.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.ABSENCE.value, "auto_leaving"),
			TestCase(42, "OFF", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "auto_leaving"),

			# state ON + Manual ON
			TestCase(42, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.AWAKE.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(42, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.PRE_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(42, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(42, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.POST_SLEEPING.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),

			TestCase(42, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.PRESENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LEAVING.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.ABSENCE.value, "manual"),
			TestCase(42, "ON", habapp_rules.system.SleepState.LOCKED.value, habapp_rules.system.PresenceState.LONG_ABSENCE.value, "manual"),
		]

		# assert that all combinations of sleeping / presence are tested
		self.assertEqual(2 * 2 * len(habapp_rules.system.SleepState) * len(habapp_rules.system.PresenceState), len(test_cases))

		for test_case in test_cases: # todo
			tests.helper.oh_item.set_state("Unittest_Light", test_case.light_value)
			tests.helper.oh_item.set_state("Unittest_Manual", test_case.manual_value)
			tests.helper.oh_item.set_state("Unittest_Presence_state", test_case.presence_value)
			tests.helper.oh_item.set_state("Unittest_Sleep_state", test_case.sleep_value)

			self.assertEqual(test_case.expected_state, self._light._get_initial_state("default"), test_case)

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()

# # pylint: disable=protected-access
# class TestLightExtended(unittest.TestCase):
# 	"""Tests cases for testing LightExtended rule."""
#
# 	def setUp(self) -> None:
# 		"""Setup test case."""
# 		self.transitions_timer_mock_patcher = unittest.mock.patch("transitions.extensions.states.Timer", spec=threading.Timer)
# 		self.addCleanup(self.transitions_timer_mock_patcher.stop)
# 		self.transitions_timer_mock = self.transitions_timer_mock_patcher.start()
#
# 		self.threading_timer_mock_patcher = unittest.mock.patch("threading.Timer", spec=threading.Timer)
# 		self.addCleanup(self.threading_timer_mock_patcher.stop)
# 		self.threading_timer_mock = self.threading_timer_mock_patcher.start()
#
# 		self.send_command_mock_patcher = unittest.mock.patch("HABApp.openhab.items.base_item.send_command", new=tests.helper.oh_item.send_command)
# 		self.addCleanup(self.send_command_mock_patcher.stop)
# 		self.send_command_mock = self.send_command_mock_patcher.start()
#
# 		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", "0")
# 		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door2", "CLOSED")
# 		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Leaving", "OFF")
# 		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone1", "ON")
# 		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone2", "OFF")
# 		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_LightExtended_state", "")
# 		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Presence", "ON")
#
# 		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
# 		self.__runner.set_up()
# 		with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_LightExtended_state", "")):
# 			self._light_extended = rules.actors.light.LightExtended("Unittest_Light")
#
# 	def test_create_graph(self):
# 		"""Create state machine graph for documentation."""
# 		presence_graph = tests.common.graph_machines.HierarchicalGraphMachineTimer(
# 			model=self._light_extended,
# 			states=self._light_extended.states,
# 			transitions=self._light_extended.trans,
# 			initial=self._light_extended.state,
# 			show_conditions=True)
#
# 		presence_graph.get_graph().draw(pathlib.Path(__file__).parent / "LightExtended.png", format="png", prog="dot")
#
# 	def tearDown(self) -> None:
# 		"""Tear down test case."""
# 		tests.helper.oh_item.remove_all_mocked_items()
# 		self.__runner.tear_down()
