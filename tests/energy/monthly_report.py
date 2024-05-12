"""Tests for monthly energy report."""
import collections
import datetime
import unittest
import unittest.mock

import HABApp.openhab.definitions.helpers.persistence_data
import HABApp.openhab.items

import habapp_rules.__version__
import habapp_rules.core.exceptions
import habapp_rules.energy.monthly_report
import tests.helper.oh_item
import tests.helper.test_case_base


# pylint: disable=protected-access
class TestFunctions(unittest.TestCase):
	"""Test all global functions."""

	def test_get_last_month_name(self):
		"""Test _get_last_month_name."""
		TestCase = collections.namedtuple("TestCase", ["month_number", "expected_name"])

		test_cases = [
			TestCase(1, "Dezember"),
			TestCase(2, "Januar"),
			TestCase(3, "Februar"),
			TestCase(4, "März"),
			TestCase(5, "April"),
			TestCase(6, "Mai"),
			TestCase(7, "Juni"),
			TestCase(8, "Juli"),
			TestCase(9, "August"),
			TestCase(10, "September"),
			TestCase(11, "Oktober"),
			TestCase(12, "November"),
		]

		today = datetime.datetime.today()
		with unittest.mock.patch("datetime.date") as mock_date:
			for test_case in test_cases:
				with self.subTest(test_case=test_case):
					mock_date.today.return_value = today.replace(month=test_case.month_number, day=1)
					self.assertEqual(test_case.expected_name, habapp_rules.energy.monthly_report._get_previous_month_name())

	def test_get_next_trigger(self):
		"""Test _get_next_trigger."""
		TestCase = collections.namedtuple("TestCase", ["current_datetime", "expected_trigger"])

		test_cases = [
			TestCase(datetime.datetime(2022, 1, 1, 0, 0, 0), datetime.datetime(2022, 2, 1, 0, 0, 0)),
			TestCase(datetime.datetime(2023, 12, 17, 2, 42, 55), datetime.datetime(2024, 1, 1, 0, 0, 0)),
			TestCase(datetime.datetime(2024, 2, 29, 23, 59, 59), datetime.datetime(2024, 3, 1, 0, 0, 0))
		]

		with unittest.mock.patch("datetime.datetime") as mock_datetime:
			for test_case in test_cases:
				with self.subTest(test_case=test_case):
					mock_datetime.now.return_value = test_case.current_datetime
					self.assertEqual(test_case.expected_trigger, habapp_rules.energy.monthly_report._get_next_trigger())


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
		energy_share = habapp_rules.energy.monthly_report.EnergyShare("Number_1", "First Number")
		self.assertEqual("Number_1", energy_share.openhab_name)
		self.assertEqual("First Number", energy_share.chart_name)
		self.assertEqual(0, energy_share.monthly_power)
		self.assertEqual("Number_1", energy_share.openhab_item.name)

		expected_item = HABApp.openhab.items.NumberItem("Number_1")
		self.assertEqual(expected_item, energy_share.openhab_item)

		# invalid init (Item not found)
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.energy.monthly_report.EnergyShare("Number_2", "Second Number")

		# invalid init (Item is not a number)
		with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
			habapp_rules.energy.monthly_report.EnergyShare("Switch_1", "Second Number")


class TestMonthlyReport(tests.helper.test_case_base.TestCaseBase):
	"""Test MonthlyReport rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Energy_Sum", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Energy_1", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Energy_2", None)

		self._energy_1 = habapp_rules.energy.monthly_report.EnergyShare("Energy_1", "Energy 1")
		self._energy_2 = habapp_rules.energy.monthly_report.EnergyShare("Energy_2", "Energy 2")
		self._mail_config = unittest.mock.MagicMock()

		self._rule = habapp_rules.energy.monthly_report.MonthlyReport("Energy_Sum", [self._energy_1, self._energy_2], None, self._mail_config, "test@test.de")

	def test_init(self):
		"""Test init."""
		TestCase = collections.namedtuple("TestCase", ["sum_in_group", "item_1_in_group", "item_2_in_group", "raises_exception"])

		test_cases = [
			TestCase(True, True, True, False),
			TestCase(True, True, False, True),
			TestCase(True, False, True, True),
			TestCase(True, False, False, True),
			TestCase(False, True, True, True),
			TestCase(False, True, False, True),
			TestCase(False, False, True, True),
			TestCase(False, False, False, True),
		]

		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				self._energy_1.openhab_item.groups = {"PersistenceGroup"} if test_case.item_1_in_group else set()
				self._energy_2.openhab_item.groups = {"PersistenceGroup"} if test_case.item_2_in_group else set()
				self._rule._item_energy_sum.groups = {"PersistenceGroup"} if test_case.sum_in_group else set()

				if test_case.raises_exception:
					with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationException):
						habapp_rules.energy.monthly_report.MonthlyReport("Energy_Sum", [self._energy_1, self._energy_2], "PersistenceGroup", self._mail_config, "test@test.de")
				else:
					habapp_rules.energy.monthly_report.MonthlyReport("Energy_Sum", [self._energy_1, self._energy_2], "PersistenceGroup", self._mail_config, "test@test.de")

	def test_init_with_debug_mode(self):
		"""Test init with debug mode."""
		self._rule = habapp_rules.energy.monthly_report.MonthlyReport("Energy_Sum", [self._energy_1, self._energy_2], None, self._mail_config, "test@test.de", True)

	def test_get_historic_value(self):
		"""Test _get_historic_value."""
		mock_item = unittest.mock.MagicMock()
		fake_persistence_data = HABApp.openhab.definitions.helpers.persistence_data.OpenhabPersistenceData()
		mock_item.get_persistence_data.return_value = fake_persistence_data

		start_time = datetime.datetime.now()
		end_time = start_time + datetime.timedelta(hours=1)

		# no data
		self.assertEqual(0, self._rule._get_historic_value(mock_item, start_time))
		mock_item.get_persistence_data.assert_called_once_with(start_time=start_time, end_time=end_time)

		# data
		fake_persistence_data.data = {"0.0": 42, "1.0": 1337}
		self.assertEqual(42, self._rule._get_historic_value(mock_item, start_time))

	def test_create_html(self):
		"""Test create_html."""
		self._rule._item_energy_sum.value = 20_123.5489135

		template_mock = unittest.mock.MagicMock()
		with (unittest.mock.patch("pathlib.Path.open"),
		      unittest.mock.patch("jinja2.Template", return_value=template_mock),
		      unittest.mock.patch("habapp_rules.energy.monthly_report._get_previous_month_name", return_value="MonthName")):
			self._rule._create_html(10_042.123456)

		template_mock.render.assert_called_once_with(
			month="MonthName",
			energy_now="20123.5",
			energy_last_month="10042.1",
			habapp_version=habapp_rules.__version__.__version__,
			chart="{{ chart }}"
		)

	def test_cb_send_energy(self):
		"""Test cb_send_energy."""
		self._rule._item_energy_sum.value = 1000
		self._energy_1.openhab_item.value = 100
		self._energy_2.openhab_item.value = 50

		with (unittest.mock.patch.object(self._rule, "_get_historic_value", side_effect=[800, 90, 45]),
		      unittest.mock.patch("habapp_rules.energy.donut_chart.create_chart", return_value="html text result") as create_chart_mock,
		      unittest.mock.patch.object(self._rule, "_create_html") as create_html_mock,
		      unittest.mock.patch("habapp_rules.energy.monthly_report._get_previous_month_name", return_value="MonthName"),
		      unittest.mock.patch.object(self._rule, "_mail") as mail_mock):
			self._rule._cb_send_energy()

		create_chart_mock.assert_called_once_with(["Energy 1", "Energy 2", "Rest"], [10, 5, 185], unittest.mock.ANY)
		create_html_mock.assert_called_once_with(200)
		mail_mock.send_message("test@test.de", "html text result", "Stromverbrauch MonthName", images={"chart": unittest.mock.ANY})
