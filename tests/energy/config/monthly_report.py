"""Test config models for monthly energy report rules."""
import HABApp
import pydantic

import habapp_rules.energy.config.monthly_report
import tests.helper.oh_item
import tests.helper.test_case_base


class TestEnergyShare(tests.helper.test_case_base.TestCaseBase):
	"""Test EnergyShare dataclass."""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Number_1", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Switch_1", None)

	def test_init(self):
		"""Test init."""
		# valid init
		energy_share = habapp_rules.energy.config.monthly_report.EnergyShare("Number_1", "First Number")
		self.assertEqual("Number_1", energy_share.energy_item.name)
		self.assertEqual("First Number", energy_share.chart_name)
		self.assertEqual(0, energy_share.monthly_power)

		expected_item = HABApp.openhab.items.NumberItem("Number_1")
		self.assertEqual(expected_item, energy_share.energy_item)

		# valid init with item
		energy_share = habapp_rules.energy.config.monthly_report.EnergyShare(expected_item, "First Number")
		self.assertEqual("Number_1", energy_share.energy_item.name)
		self.assertEqual("First Number", energy_share.chart_name)
		self.assertEqual(0, energy_share.monthly_power)

		# invalid init (Item not found)
		with self.assertRaises(pydantic.ValidationError):
			habapp_rules.energy.config.monthly_report.EnergyShare("Number_2", "Second Number")

		# invalid init (Item is not a number)
		with self.assertRaises(pydantic.ValidationError):
			habapp_rules.energy.config.monthly_report.EnergyShare("Switch_1", "Second Number")
