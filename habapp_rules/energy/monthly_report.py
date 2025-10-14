"""Module for sending the monthly energy consumption."""

import datetime
import logging
import pathlib
import tempfile

import dateutil.relativedelta
import HABApp
import jinja2
import multi_notifier.connectors.connector_mail

import habapp_rules
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.energy.config.monthly_report
import habapp_rules.energy.donut_chart
import habapp_rules.energy.helper

LOGGER = logging.getLogger(__name__)

MONTH_MAPPING = {1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni", 7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember"}


def _get_previous_month_name() -> str:
    """Get name of the previous month.

    if other languages are required, the global dict must be replaced

    Returns:
        name of current month
    """
    today = datetime.datetime.now()
    last_month = today.replace(day=1) - datetime.timedelta(days=1)

    return MONTH_MAPPING[last_month.month]


class MonthlyReport(HABApp.Rule):
    """Rule for sending the monthly energy consumption.

    # Config
    config = habapp_rules.energy.config.monthly_report.MonthlyReportConfig(
            items=habapp_rules.energy.config.monthly_report.MonthlyReportItems(
                    energy_sum="Total Energy"
            ),
            parameter=habapp_rules.energy.config.monthly_report.MonthlyReportParameter(
                    known_energy_shares=[
                            habapp_rules.energy.config.monthly_report.EnergyShare("Dishwasher_Energy", "Dishwasher"),
                            habapp_rules.energy.config.monthly_report.EnergyShare("Light", "Light")
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
    habapp_rules.energy.monthly_report.MonthlyReport("Total_Energy", known_energy_share, "Group_RRD4J", config_mail, "test@test.de")
    """

    def __init__(self, config: habapp_rules.energy.config.monthly_report.MonthlyReportConfig) -> None:
        """Initialize the rule.

        Args:
            config: config for the monthly energy report rule

        Raises:
            habapp_rules.core.exceptions.HabAppRulesConfigurationError: if config is not valid
        """
        self._config = config
        HABApp.Rule.__init__(self)
        self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, config.items.energy_sum.name)
        self._mail = multi_notifier.connectors.connector_mail.Mail(config.parameter.config_mail)

        self._mail = multi_notifier.connectors.connector_mail.Mail(config.parameter.config_mail)

        if config.parameter.persistence_group_name is not None:
            # check if all energy items are in the given persistence group
            items_to_check = [config.items.energy_sum] + [item for share in config.parameter.known_energy_shares for item in share.get_items_as_list]
            not_in_persistence_group = [item.name for item in items_to_check if config.parameter.persistence_group_name not in item.groups]
            if not_in_persistence_group:
                msg = f"The following OpenHAB items are not in the persistence group '{config.parameter.persistence_group_name}': {not_in_persistence_group}"
                raise habapp_rules.core.exceptions.HabAppRulesConfigurationError(msg)

        self.run.at(self.run.trigger.time("00:00:00").only_on(self.run.filter.days(1)), self._cb_send_energy)

        if config.parameter.debug:
            self._instance_logger.warning("Debug mode is active!")
            self.run.soon(self._cb_send_energy)
        self._instance_logger.info(f"Successfully initiated monthly consumption rule for {config.items.energy_sum.name}.")

    def _create_html(self, energy_sum_month: float) -> str:
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

        Returns:
            html with replaced values
        """
        with (pathlib.Path(__file__).parent / "monthly_report_template.html").open(encoding="utf-8") as template_file:
            html_template = template_file.read()

        return jinja2.Template(html_template).render(
            month=_get_previous_month_name(),
            energy_now=f"{self._config.items.energy_sum.value:.1f}",
            energy_last_month=f"{energy_sum_month:.1f}",
            habapp_version=habapp_rules.__version__,
            chart="{{ chart }}",  # this is needed to not replace the chart from the mail-template
        )

    def _cb_send_energy(self) -> None:
        """Send the mail with the energy consumption of the last month."""
        self._instance_logger.debug("Send energy consumption was triggered.")
        # get values
        now = datetime.datetime.now()
        last_month = now - dateutil.relativedelta.relativedelta(months=1)

        energy_sum_month = self._config.items.energy_sum.value - habapp_rules.energy.helper.get_historic_value(self._config.items.energy_sum, last_month)
        for share in self._config.parameter.known_energy_shares:
            share.monthly_power = share.get_energy_since(last_month)

        # calculate unknown energy share
        energy_unknown = energy_sum_month - sum(share.monthly_power for share in self._config.parameter.known_energy_shares)

        # filter energy shares which are zero
        shares_for_chart = [share for share in self._config.parameter.known_energy_shares if share.monthly_power > 0]

        with tempfile.TemporaryDirectory() as temp_dir_name:
            # create plot
            labels = [share.chart_name for share in shares_for_chart] + ["Rest"]
            values = [share.monthly_power for share in shares_for_chart] + [energy_unknown]
            chart_path = pathlib.Path(temp_dir_name) / "chart.png"
            habapp_rules.energy.donut_chart.create_chart(labels, values, chart_path)

            # get html
            html = self._create_html(energy_sum_month)

            # send mail
            self._mail.send_message(self._config.parameter.recipients, html, f"Stromverbrauch {_get_previous_month_name()}", images={"chart": str(chart_path)})

        self._instance_logger.info(f"Successfully sent energy consumption mail to {self._config.parameter.recipients}.")
