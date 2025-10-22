"""Tests for monthly energy report."""

import collections
import datetime
import unittest
import unittest.mock

import HABApp.openhab.items
import multi_notifier.connectors.connector_mail

import habapp_rules
import habapp_rules.core.exceptions
import habapp_rules.energy.config.monthly_report
import habapp_rules.energy.monthly_report
import tests.helper.oh_item
import tests.helper.test_case_base


class TestFunctions(unittest.TestCase):
    """Test all global functions."""

    def test_get_last_month_name(self) -> None:
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
        with unittest.mock.patch("datetime.datetime") as datetime_mock:
            for test_case in test_cases:
                with self.subTest(test_case=test_case):
                    datetime_mock.now.return_value = today.replace(month=test_case.month_number, day=1)
                    self.assertEqual(test_case.expected_name, habapp_rules.energy.monthly_report._get_previous_month_name())


class TestMonthlyReport(tests.helper.test_case_base.TestCaseBase):
    """Test MonthlyReport rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Energy_Sum", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Energy_1", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Energy_2", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Energy_3", None)

        self._energy_1 = habapp_rules.energy.config.monthly_report.EnergyShare("Energy_1", "Energy 1")
        self._energy_2 = habapp_rules.energy.config.monthly_report.EnergyShare("Energy_2", "Energy 2")
        self._energy_3 = habapp_rules.energy.config.monthly_report.EnergyShare("Energy_3", "Energy 3")
        self._mail_config = multi_notifier.connectors.connector_mail.MailConfig(user="User", password="Password", smtp_host="smtp.test.de", smtp_port=587)  # noqa: S106

        config = habapp_rules.energy.config.monthly_report.MonthlyReportConfig(
            items=habapp_rules.energy.config.monthly_report.MonthlyReportItems(energy_sum="Energy_Sum"),
            parameter=habapp_rules.energy.config.monthly_report.MonthlyReportParameter(known_energy_shares=[self._energy_1, self._energy_2], config_mail=self._mail_config, recipients=["test@test.de"]),
        )

        self._rule = habapp_rules.energy.monthly_report.MonthlyReport(config)

    def test_init(self) -> None:
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
                self._energy_1.energy_item.groups = {"PersistenceGroup"} if test_case.item_1_in_group else set()
                self._energy_2.energy_item.groups = {"PersistenceGroup"} if test_case.item_2_in_group else set()
                self._rule._config.items.energy_sum.groups = {"PersistenceGroup"} if test_case.sum_in_group else set()

                config = habapp_rules.energy.config.monthly_report.MonthlyReportConfig(
                    items=habapp_rules.energy.config.monthly_report.MonthlyReportItems(energy_sum="Energy_Sum"),
                    parameter=habapp_rules.energy.config.monthly_report.MonthlyReportParameter(
                        known_energy_shares=[self._energy_1, self._energy_2], config_mail=self._mail_config, recipients=["test@test.de"], persistence_group_name="PersistenceGroup"
                    ),
                )

                if test_case.raises_exception:
                    with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
                        habapp_rules.energy.monthly_report.MonthlyReport(config)
                else:
                    habapp_rules.energy.monthly_report.MonthlyReport(config)

    def test_init_with_debug_mode(self) -> None:
        """Test init with debug mode."""
        config = habapp_rules.energy.config.monthly_report.MonthlyReportConfig(
            items=habapp_rules.energy.config.monthly_report.MonthlyReportItems(energy_sum="Energy_Sum"),
            parameter=habapp_rules.energy.config.monthly_report.MonthlyReportParameter(known_energy_shares=[self._energy_1, self._energy_2], config_mail=self._mail_config, recipients=["test@test.de"], debug=True),
        )

        self._rule = habapp_rules.energy.monthly_report.MonthlyReport(config)

    def test_create_html(self) -> None:
        """Test create_html."""
        self._rule._config.items.energy_sum.value = 20_123.5489135

        template_mock = unittest.mock.MagicMock()
        with unittest.mock.patch("jinja2.Template", return_value=template_mock), unittest.mock.patch("habapp_rules.energy.monthly_report._get_previous_month_name", return_value="MonthName"):
            self._rule._create_html(10_042.123456)

        template_mock.render.assert_called_once_with(month="MonthName", energy_now="20123.5", energy_last_month="10042.1", habapp_version=habapp_rules.__version__, chart="{{ chart }}")

    def test_cb_send_energy(self) -> None:
        """Test cb_send_energy."""
        self._rule._config.items.energy_sum.value = 1000
        self._energy_1.energy_item.value = 100
        self._energy_2.energy_item.value = 50
        self._energy_3.energy_item.value = 5

        with (
            unittest.mock.patch("habapp_rules.energy.helper.get_historic_value", side_effect=[800, 90, 45, 100]),
            unittest.mock.patch("habapp_rules.energy.donut_chart.create_chart", return_value="html text result") as create_chart_mock,
            unittest.mock.patch.object(self._rule, "_create_html") as create_html_mock,
            unittest.mock.patch("habapp_rules.energy.monthly_report._get_previous_month_name", return_value="MonthName"),
            unittest.mock.patch.object(self._rule, "_mail") as mail_mock,
        ):
            self._rule._cb_send_energy()

        create_chart_mock.assert_called_once_with(["Energy 1", "Energy 2", "Rest"], [10, 5, 185], unittest.mock.ANY)
        create_html_mock.assert_called_once_with(200)
        mail_mock.send_message("test@test.de", "html text result", "Stromverbrauch MonthName", images={"chart": unittest.mock.ANY})
