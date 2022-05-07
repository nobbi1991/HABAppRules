"""Test Light rule."""
import pathlib
import threading
import unittest
import unittest.mock

import HABApp.rule.rule

import rules.common.state_machine_rule
import rules.actors.light
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

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", "0")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door2", "CLOSED")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Leaving", "OFF")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone1", "ON")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone2", "OFF")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_system_presence_Presence_state", "")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Presence", "ON")

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()
		with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_Light_state", "")):
			self._light = rules.actors.light.Light("Unittest_Light")

	def test_create_graph(self):
		"""Create state machine graph for documentation."""
		presence_graph = tests.common.graph_machines.HierarchicalGraphMachineTimer(
			model=self._light,
			states=self._light.states,
			transitions=self._light.trans,
			initial=self._light.state,
			show_conditions=True)

		presence_graph.get_graph().draw(pathlib.Path(__file__).parent / "Light.png", format="png", prog="dot")

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()


# pylint: disable=protected-access
class TestLightExtended(unittest.TestCase):
	"""Tests cases for testing LightExtended rule."""

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

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Light", "0")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.ContactItem, "Unittest_Door2", "CLOSED")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Leaving", "OFF")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone1", "ON")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Phone2", "OFF")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "rules_actors_light_LightExtended_state", "")
		# tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Presence", "ON")

		self.__runner = tests.helper.rule_runner.SimpleRuleRunner()
		self.__runner.set_up()
		with unittest.mock.patch.object(rules.common.state_machine_rule.StateMachineRule, "_create_additional_item", return_value=HABApp.openhab.items.string_item.StringItem("rules_actors_light_LightExtended_state", "")):
			self._light_extended = rules.actors.light.LightExtended("Unittest_Light")

	def test_create_graph(self):
		"""Create state machine graph for documentation."""
		presence_graph = tests.common.graph_machines.HierarchicalGraphMachineTimer(
			model=self._light_extended,
			states=self._light_extended.states,
			transitions=self._light_extended.trans,
			initial=self._light_extended.state,
			show_conditions=True)

		presence_graph.get_graph().draw(pathlib.Path(__file__).parent / "LightExtended.png", format="png", prog="dot")

	def tearDown(self) -> None:
		"""Tear down test case."""
		tests.helper.oh_item.remove_all_mocked_items()
		self.__runner.tear_down()
