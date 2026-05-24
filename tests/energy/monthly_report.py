"""Tests for monthly energy report."""

import collections
import datetime
import json
import pathlib
import tempfile
import unittest
import unittest.mock

from HABApp.openhab.items import NumberItem
from multi_notifier.connectors.connector_mail import MailConfig

from habapp_rules import __version__
from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.energy.config.monthly_report import EnergyShare, MonthlyReportConfig, MonthlyReportItems, MonthlyReportParameter
from habapp_rules.energy.monthly_report import MONTH_MAPPING, MonthlyReport, _get_current_month_name
from tests.helper.oh_item import (
    add_mock_item,
)
from tests.helper.test_case_base import TestCaseBase


class TestFunctions(unittest.TestCase):
    """Test all global functions."""

    def test_get_current_month_name(self) -> None:
        """Test _get_current_month_name."""
        today = datetime.datetime.today()
        with unittest.mock.patch("datetime.datetime") as datetime_mock:
            for month_number in range(1, 13):
                with self.subTest(month_number=month_number):
                    datetime_mock.now.return_value = today.replace(month=month_number, day=1)
                    self.assertEqual(MONTH_MAPPING[month_number], _get_current_month_name())


class TestMonthlyReport(TestCaseBase):
    """Test MonthlyReport rule."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Energy_Sum", None)
        add_mock_item(NumberItem, "Energy_1", None)
        add_mock_item(NumberItem, "Energy_2", None)
        add_mock_item(NumberItem, "Energy_3", None)

        self._energy_1 = EnergyShare("Energy_1", "Energy 1")
        self._energy_2 = EnergyShare("Energy_2", "Energy 2")
        self._energy_3 = EnergyShare("Energy_3", "Energy 3")
        self._mail_config = MailConfig(user="User", password="Password", smtp_host="smtp.test.de", smtp_port=587)  # noqa: S106

        config = MonthlyReportConfig(
            items=MonthlyReportItems(energy_sum="Energy_Sum"),
            parameter=MonthlyReportParameter(known_energy_shares=[self._energy_1, self._energy_2], config_mail=self._mail_config, recipients=["test@test.de"]),
        )

        self._rule = MonthlyReport(config)

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

                config = MonthlyReportConfig(
                    items=MonthlyReportItems(energy_sum="Energy_Sum"),
                    parameter=MonthlyReportParameter(known_energy_shares=[self._energy_1, self._energy_2], config_mail=self._mail_config, recipients=["test@test.de"], persistence_group_name="PersistenceGroup"),
                )

                if test_case.raises_exception:
                    with self.assertRaises(HabAppRulesConfigurationError):
                        MonthlyReport(config)
                else:
                    MonthlyReport(config)

    def test_init_with_debug_mode(self) -> None:
        """Test init with debug mode."""
        config = MonthlyReportConfig(
            items=MonthlyReportItems(energy_sum="Energy_Sum"),
            parameter=MonthlyReportParameter(known_energy_shares=[self._energy_1, self._energy_2], config_mail=self._mail_config, recipients=["test@test.de"], debug=True),
        )

        self._rule = MonthlyReport(config)

    def test_create_html(self) -> None:
        """Test create_html."""
        self._rule._config.items.energy_sum.value = 20_123.5489135

        template_mock = unittest.mock.MagicMock()
        with unittest.mock.patch("jinja2.Template", return_value=template_mock), unittest.mock.patch("habapp_rules.energy.monthly_report._get_current_month_name", return_value="MonthName"):
            self._rule._create_html(10_042.123456)

        template_mock.render.assert_called_once_with(month="MonthName", energy_now="20123.5", energy_last_month="10042.1", habapp_version=__version__, show_history=True)

    def test_cb_send_energy(self) -> None:
        """Test cb_send_energy."""
        self._rule._config.items.energy_sum.value = 1000
        self._energy_1.energy_item.value = 100
        self._energy_2.energy_item.value = 100_000  # unrealistic value
        self._energy_3.energy_item.value = 5

        with (
            unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[800]),
            unittest.mock.patch("habapp_rules.energy.config.monthly_report.get_historic_value", side_effect=[90, 1000, 100]),
            unittest.mock.patch("habapp_rules.energy.monthly_report.create_pie_chart") as create_pie_chart_mock,
            unittest.mock.patch("habapp_rules.energy.monthly_report.create_history_chart") as create_history_chart_mock,
            unittest.mock.patch.object(self._rule, "_get_monthly_history", return_value=(["Jan", "Feb"], [100.0, 200.0])) as history_mock,
            unittest.mock.patch.object(self._rule, "_create_html") as create_html_mock,
            unittest.mock.patch("habapp_rules.energy.monthly_report._get_current_month_name", return_value="MonthName"),
            unittest.mock.patch.object(self._rule, "_mail") as mail_mock,
        ):
            self._rule._cb_send_energy()

        create_pie_chart_mock.assert_called_once_with(["Energy 1", "Rest"], [10, 190.0], unittest.mock.ANY)
        history_mock.assert_called_once_with(12)
        create_history_chart_mock.assert_called_once_with(["Jan", "Feb"], [100.0, 200.0], unittest.mock.ANY)
        create_html_mock.assert_called_once_with(200, show_history=True)
        mail_mock.send_message.assert_called_once_with(["test@test.de"], unittest.mock.ANY, "Stromverbrauch MonthName", images={"chart": unittest.mock.ANY, "history_chart": unittest.mock.ANY})

    def test_cb_send_energy_disabled(self) -> None:
        """Test cb_send_energy with history_months=0 disables history chart."""
        self._rule._config.parameter.history_months = 0
        self._rule._config.items.energy_sum.value = 1000
        self._energy_1.energy_item.value = 100
        self._energy_2.energy_item.value = 100_000
        self._energy_3.energy_item.value = 5

        with (
            unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[800]),
            unittest.mock.patch("habapp_rules.energy.config.monthly_report.get_historic_value", side_effect=[90, 1000, 100]),
            unittest.mock.patch("habapp_rules.energy.monthly_report.create_pie_chart"),
            unittest.mock.patch("habapp_rules.energy.monthly_report.create_history_chart") as create_history_chart_mock,
            unittest.mock.patch.object(self._rule, "_get_monthly_history") as history_mock,
            unittest.mock.patch.object(self._rule, "_create_html"),
            unittest.mock.patch("habapp_rules.energy.monthly_report._get_current_month_name", return_value="MonthName"),
            unittest.mock.patch.object(self._rule, "_mail") as mail_mock,
        ):
            self._rule._cb_send_energy()

        history_mock.assert_not_called()
        create_history_chart_mock.assert_not_called()
        call_kwargs = mail_mock.send_message.call_args.kwargs
        self.assertNotIn("history_chart", call_kwargs["images"])

    def test_cb_send_energy_error(self) -> None:
        """Test _cb_send_energy."""
        with unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[None]), unittest.mock.patch("habapp_rules.energy.monthly_report.LOGGER") as logger_mock:
            self._rule._cb_send_energy()

        logger_mock.error.assert_called_once()

    def test_get_monthly_history_normal(self) -> None:
        """All months have valid persistence data."""
        with unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[1000.0, 900.0, 750.0, 600.0]):
            labels, values = self._rule._get_monthly_history(3)

        self.assertEqual(3, len(labels))
        self.assertEqual(3, len(values))
        self.assertAlmostEqual(150.0, values[0])  # oldest: 750-600
        self.assertAlmostEqual(150.0, values[1])  # middle: 900-750
        self.assertAlmostEqual(100.0, values[2])  # most recent: 1000-900

    def test_get_monthly_history_missing_data(self) -> None:
        """Zero persistence value (no data) yields 0.0 consumption."""
        with unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[1000.0, 0.0, 800.0]):
            _labels, values = self._rule._get_monthly_history(2)

        self.assertAlmostEqual(0.0, values[0])  # oldest: boundaries[2]=800 truthy, max(0, 0-800)=0
        self.assertAlmostEqual(0.0, values[1])  # recent: boundaries[1]=0 → guard → 0.0

    def test_get_monthly_history_equal_values(self) -> None:
        """Equal consecutive meter readings produce no warning and zero consumption."""
        with (
            unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[1000.0, 1000.0, 1000.0]),
            unittest.mock.patch.object(self._rule._instance_logger, "warning") as warn_mock,
        ):
            _labels, values = self._rule._get_monthly_history(2)

        warn_mock.assert_not_called()
        self.assertAlmostEqual(0.0, values[0])
        self.assertAlmostEqual(0.0, values[1])

    def test_get_monthly_history_non_monotonic(self) -> None:
        """Older meter reading greater than newer triggers a warning."""
        # energy_values collected newest→oldest: [900, 1000, 750]
        # index 1 (1000 kWh) > index 0 (900 kWh) → meter appeared to go backward
        with (
            unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[900.0, 1000.0, 750.0]),
            unittest.mock.patch.object(self._rule._instance_logger, "warning") as warn_mock,
        ):
            self._rule._get_monthly_history(2)

        warn_mock.assert_called_once()

    def test_get_monthly_history_non_monotonic_newer_zero(self) -> None:
        """Non-monotonic pair is skipped without warning when the newer value is zero."""
        # energy_values: [0, 1000, 750] — newer=0 short-circuits the check
        with (
            unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[0.0, 1000.0, 750.0]),
            unittest.mock.patch.object(self._rule._instance_logger, "warning") as warn_mock,
        ):
            self._rule._get_monthly_history(2)

        warn_mock.assert_not_called()


class TestMonthlyReportHistoryCache(TestCaseBase):
    """Test JSON caching in HistoricValueProvider."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)
        add_mock_item(NumberItem, "Energy_Sum", None)
        mail_config = MailConfig(user="u", password="p", smtp_host="h", smtp_port=587)  # noqa: S106
        self._temp_dir = tempfile.TemporaryDirectory()
        self._cache_path = pathlib.Path(self._temp_dir.name) / "cache.json"
        self._rule = MonthlyReport(
            MonthlyReportConfig(
                items=MonthlyReportItems(energy_sum="Energy_Sum"),
                parameter=MonthlyReportParameter(config_mail=mail_config, recipients=["r@r.de"], history_cache_path=self._cache_path),
            )
        )
        self._provider = self._rule._historic_value_provider_sum

    def tearDown(self) -> None:
        """Teardown test case."""
        TestCaseBase.tearDown(self)
        self._temp_dir.cleanup()

    def test_load_history_cache_no_file(self) -> None:
        """Missing cache file returns empty dict."""
        self.assertEqual({}, self._provider._load_cache())

    def test_load_history_cache_valid(self) -> None:
        """Valid cache file is loaded correctly."""
        self._cache_path.write_text('{"2025-01": 1000.0}', encoding="utf-8")
        self.assertEqual({"2025-01": 1000.0}, self._provider._load_cache())

    def test_load_history_cache_invalid_json(self) -> None:
        """Corrupt cache file returns empty dict and logs a warning."""
        self._cache_path.write_text("not json", encoding="utf-8")
        with unittest.mock.patch("habapp_rules.energy.monthly_report.LOGGER") as logger_mock:
            result = self._provider._load_cache()
        self.assertEqual({}, result)
        logger_mock.warning.assert_called_once()

    def test_save_history_cache(self) -> None:
        """Cache data is written to the JSON file."""
        data = {"2025-01": 1000.0, "2025-02": 1100.0}
        self._provider._cached_values = data
        self._provider._save_cache()
        self.assertEqual(data, json.loads(self._cache_path.read_text(encoding="utf-8")))

    def test_get_monthly_history_cache_miss(self) -> None:
        """Cache miss queries persistence and writes the values to file."""
        with unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[1000.0, 900.0, 750.0]):
            labels, _values = self._rule._get_monthly_history(2)

        self.assertEqual(2, len(labels))
        cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
        self.assertEqual(3, len(cache))

    def test_get_monthly_history_cache_hit(self) -> None:
        """Fully cached month boundaries skip persistence and do not rewrite the file."""
        with unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value", side_effect=[1000.0, 900.0, 750.0]):
            self._rule._get_monthly_history(2)

        with (
            unittest.mock.patch("habapp_rules.energy.monthly_report.get_historic_value") as get_mock,
            unittest.mock.patch.object(self._provider, "_save_cache") as save_mock,
        ):
            _labels, values = self._rule._get_monthly_history(2)

        get_mock.assert_not_called()
        save_mock.assert_not_called()
        self.assertAlmostEqual(150.0, values[0])  # 900 - 750
        self.assertAlmostEqual(100.0, values[1])  # 1000 - 900
