"""Module for sending the monthly energy consumption."""

import datetime
import json
import logging
import os
import pathlib
import tempfile
from datetime import timedelta

import dateutil.relativedelta
import jinja2
import multi_notifier.connectors.connector_mail
from HABApp.openhab.items import NumberItem

from habapp_rules import __version__
from habapp_rules.core.base import RuleBase
from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.energy.charts import create_history_chart, create_pie_chart
from habapp_rules.energy.config.monthly_report import MonthlyReportConfig
from habapp_rules.energy.helper import get_historic_value

LOGGER = logging.getLogger(__name__)

MONTH_MAPPING = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni", 7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}
SHORT_MONTH_MAPPING = {1: "Jan", 2: "Feb", 3: "Mär", 4: "Apr", 5: "Mai", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dez"}


def _get_month_name(month: int) -> str:
    """Get name of the given month.

    if other languages are required, the global dict must be replaced

    Args:
        month: month number (1-12)

    Returns:
        name of the given month
    """
    return MONTH_MAPPING[month]


class HistoricValueProvider:
    """Fetches and caches energy meter readings at the start of each month."""

    def __init__(self, item: NumberItem, cache_path: pathlib.Path | None) -> None:
        """Initialize the provider.

        Args:
            item: OpenHAB NumberItem holding the cumulative energy meter reading
            cache_path: path to a JSON cache file; None disables caching
        """
        self._item = item
        self._cache_path = cache_path
        self._cached_values: dict[str, float] = self._load_cache()  # keys are "YYYY-MM"

    def _load_cache(self) -> dict[str, float]:
        """Load cached values from JSON file.

        Returns:
            mapping of "YYYY-MM" keys to energy boundary values, empty dict on error
        """
        if self._cache_path is None or not self._cache_path.exists():
            return {}
        try:
            return json.loads(self._cache_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            LOGGER.warning("Could not read history cache, starting fresh.")
            return {}

    def _save_cache(self) -> None:
        """Persist cached values to the JSON file.

        The data is written to a uniquely named temporary file in the same directory and then atomically moved onto the cache file via ``os.replace``. This keeps the cache consistent even when multiple ``MonthlyReport`` instances (e.g. a debug and a productive one) write to the same file concurrently or the process is killed mid-write.
        """
        if self._cache_path is None:
            return
        fd, tmp_name = tempfile.mkstemp(dir=self._cache_path.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            json.dump(self._cached_values, tmp_file, indent=2)
        pathlib.Path(tmp_name).replace(self._cache_path)

    def get_start_of_month_value(self, year: int, month: int) -> float:
        """Return the meter reading at the start of the given month, using the cache.

        Args:
            year: calendar year
            month: calendar month (1-12)

        Returns:
            energy meter value at midnight on the first of the month
        """
        request_time = datetime.datetime(year, month, 1)
        cache_key = request_time.strftime("%Y-%m")

        if cache_key in self._cached_values:
            return self._cached_values[cache_key]

        value = get_historic_value(self._item, request_time)

        # a falsy value means the lookup failed (no persistence data); do not cache it, otherwise a single bad read would be served permanently
        if value:
            self._cached_values[cache_key] = value
            self._save_cache()

        return value


class MonthlyReport(RuleBase):
    """Rule for sending the monthly energy consumption.

    # Config
    config = MonthlyReportConfig(
            items=MonthlyReportItems(
                    energy_sum="Total Energy"
            ),
            parameter=MonthlyReportParameter(
                    known_energy_shares=[
                            EnergyShare("Dishwasher_Energy", "Dishwasher"),
                            EnergyShare("Light", "Light")
                    ],
                    config_mail=multi_notifier.connectors.connector_mail.MailConfig(
                            user="sender@test.de",
                            password="fancy_password",
                            smtp_host="smtp.test.de",
                            smtp_port=587
                    ),
                    recipients=["test@test.de"],
            )
    )

    # Rule init
    MonthlyReport("Total_Energy", known_energy_share, "Group_RRD4J", config_mail, "test@test.de")
    """

    def __init__(self, config: MonthlyReportConfig) -> None:
        """Initialize the rule.

        Args:
            config: config for the monthly energy report rule

        Raises:
            HabAppRulesConfigurationError: if config is not valid
        """
        self._config = config
        RuleBase.__init__(self, config.items.energy_sum.name)
        self._mail = multi_notifier.connectors.connector_mail.Mail(config.parameter.config_mail)

        if config.parameter.persistence_group_name is not None:
            # check if all energy items are in the given persistence group
            items_to_check = [config.items.energy_sum] + [item for share in config.parameter.known_energy_shares for item in share.get_items_as_list]
            not_in_persistence_group = [item.name for item in items_to_check if config.parameter.persistence_group_name not in item.groups]
            if not_in_persistence_group:
                msg = f"The following OpenHAB items are not in the persistence group '{config.parameter.persistence_group_name}': {not_in_persistence_group}"
                raise HabAppRulesConfigurationError(msg)

        self._historic_value_provider_sum = HistoricValueProvider(config.items.energy_sum, config.parameter.history_cache_path)

        self.run.at(self.run.trigger.time("00:00:00").only_on(self.run.filter.days(1)), self._cb_send_energy)

        if config.parameter.debug:
            self._instance_logger.warning("Debug mode is active!")
            self.run.soon(self._cb_send_energy)
        self._log_init_done()

    def _create_html(self, energy_sum_month: float, month_name: str, *, show_history: bool = True) -> str:
        """Create html which will be sent by the mail.

        The template was created by https://app.bootstrapemail.com/editor/documents with the following input:

        <html>
          <head>
            <meta http-equiv="Content-Type" content="text/html; charset=utf-8" />
            <style>
            </style>
          </head>
          <body class="bg-light">
            <div class="container">
              <div class="card my-10">
                <div class="card-body">
                  <h1 class="h3 mb-2">Strom Verbrauch</h1>
                  <h5 class="text-teal-700">von Februar</h5>
                  <hr>
                  <div class="space-y-3">
                    <p class="text-gray-700">Aktueller Zählerstand: <b>7000 kWh</b>.</p>
                    <p class="text-gray-700">Hier die Details:</p>
                    <p><img src="https://www.datylon.com/hubfs/Datylon%20Website2020/Datylon%20Chart%20library/Chart%20pages/Pie%20Chart/datylon-chart-library-pie-chart-intro-example.svg" alt="Italian Trulli" align="left">
                    </p>
                  </div>
                  <hr>
                   <p style="font-size: 0.6em">Generated with habapp_rules version = 20.0.3</p>
                </div>
              </div>
            </div>
          </body>
        </html>

        Args:
            energy_sum_month: sum value for the current month
            month_name: name of the month the report is about
            show_history: if True, the history chart section is rendered in the HTML

        Returns:
            html with replaced values
        """
        with (pathlib.Path(__file__).parent / "monthly_report_template.html").open(encoding="utf-8") as template_file:
            html_template = template_file.read()

        return jinja2.Template(html_template).render(
            month=month_name,
            energy_now=f"{self._config.items.energy_sum.value:.1f}",
            energy_last_month=f"{energy_sum_month:.1f}",
            habapp_version=__version__,
            show_history=show_history,
        )

    def _get_monthly_history(self, num_months: int) -> tuple[list[str], list[float]]:
        """Retrieve monthly consumption for the last num_months completed months.

        Args:
            num_months: number of months to include, ordered oldest → newest

        Returns:
            tuple of (month_labels, consumption_values_kWh)
        """
        now = datetime.datetime.now()
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        energy_values: list[float] = []
        for i in range(num_months + 1):
            t = first_of_this_month - dateutil.relativedelta.relativedelta(months=i)
            energy_values.append(self._historic_value_provider_sum.get_start_of_month_value(t.year, t.month))

        for i in range(len(energy_values) - 1):
            newer, older = energy_values[i], energy_values[i + 1]
            if older and newer and older > newer:
                t_newer = first_of_this_month - dateutil.relativedelta.relativedelta(months=i)
                t_older = first_of_this_month - dateutil.relativedelta.relativedelta(months=i + 1)
                self._instance_logger.warning(f"Energy meter value is not monotonically increasing: {t_older.strftime('%Y-%m')} ({older:.1f} kWh) > {t_newer.strftime('%Y-%m')} ({newer:.1f} kWh)")

        labels: list[str] = []
        values: list[float] = []
        for i in range(num_months, 0, -1):
            month_dt = first_of_this_month - dateutil.relativedelta.relativedelta(months=i)
            labels.append(SHORT_MONTH_MAPPING[month_dt.month])
            values.append(max(0.0, energy_values[i - 1] - energy_values[i]) if energy_values[i] else 0.0)

        return labels, values

    def _cb_send_energy(self) -> None:
        """Send the mail with the energy consumption of the current month so far."""
        self._instance_logger.debug("Send energy consumption was triggered.")

        # get start of month -> normal case: if triggered at 00:00 of the first day of the month, start_of_month is the start of the previous month, otherwise get first day of current month
        now = datetime.datetime.now()
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        if now.day == 1:
            start_of_month = (start_of_month - timedelta(days=1)).replace(day=1)
        month_name = _get_month_name(start_of_month.month)

        # get energy sum at start of month
        if not (energy_start_of_month := self._historic_value_provider_sum.get_start_of_month_value(start_of_month.year, start_of_month.month)):
            self._instance_logger.error(f"Could not get historic value 'energy_sum' for start of month ({start_of_month}).")
            return

        # get energy since start of month + energy of every share
        energy_sum_month = self._config.items.energy_sum.value - energy_start_of_month
        for share in self._config.parameter.known_energy_shares:
            monthly_power = share.get_energy_since(start_of_month)
            if monthly_power > energy_sum_month:
                self._instance_logger.warning(f"Power of {share.chart_name} is greater than the energy sum. {monthly_power} > {energy_sum_month} -> set it to 0")
                monthly_power = 0
            share.monthly_power = monthly_power

        energy_unknown = energy_sum_month - sum(share.monthly_power for share in self._config.parameter.known_energy_shares)
        shares_for_chart = [share for share in self._config.parameter.known_energy_shares if share.monthly_power > 0]

        # create images / charts
        with tempfile.TemporaryDirectory() as temp_dir_name:
            labels = [share.chart_name for share in shares_for_chart] + ["Rest"]
            values = [share.monthly_power for share in shares_for_chart] + [energy_unknown]
            chart_path = pathlib.Path(temp_dir_name) / "pie_chart.png"
            create_pie_chart(labels, values, chart_path)

            images: dict[str, pathlib.Path] = {"chart": chart_path}
            if self._config.parameter.history_months > 0:
                history_labels, history_values = self._get_monthly_history(self._config.parameter.history_months)
                history_chart_path = pathlib.Path(temp_dir_name) / "history_chart.png"
                create_history_chart(history_labels, history_values, history_chart_path)
                images["history_chart"] = history_chart_path

            html = self._create_html(energy_sum_month, month_name, show_history=self._config.parameter.history_months > 0)
            self._mail.send_message(self._config.parameter.recipients, html, f"Stromverbrauch {month_name}", images=images)

        self._instance_logger.info(f"Successfully sent energy consumption mail to {self._config.parameter.recipients}.")
