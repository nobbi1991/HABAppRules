"""Test energy save switch rules."""
import collections

import HABApp.rule.rule

import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.core.state_machine_rule
import habapp_rules.energy.config.virtual_energy_meter
import habapp_rules.energy.virtual_energy_meter
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer


# pylint: disable=protected-access,no-member,too-many-public-methods
class TestVirtualEnergyMeterSwitch(tests.helper.test_case_base.TestCaseBaseStateMachine):
	"""Tests cases for testing VirtualEnergyMeterSwitch."""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Switch_Power")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Switch_Energy")

		self._config = habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchConfig(
			items=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchItems(
				monitored_switch="Unittest_Switch",
				power_output="Unittest_Switch_Power",
				energy_output="Unittest_Switch_Energy"
			),
			parameter=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchParameter(
				power=100
			)
		)

		self._rule = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterSwitch(self._config)

	def test_get_energy_countdown_time(self) -> None:

		TestCase = collections.namedtuple("TestCase", "power, time")

		test_cases = [
			TestCase(power=10, time=3600),
			TestCase(power=100, time=360)
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self._rule._config.parameter.power = test_case.power
				self.assertEqual(test_case.time, self._rule._get_energy_countdown_time())

