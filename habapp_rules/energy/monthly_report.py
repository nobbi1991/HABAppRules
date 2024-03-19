"""Module for sending the monthly energy consumption."""
import dataclasses
import datetime
import logging
import pathlib
import tempfile

import HABApp
import HABApp.core.internals
import dateutil.relativedelta
import jinja2
import multi_notifier.connectors.connector_mail

import habapp_rules.__version__
import habapp_rules.core.exceptions
import habapp_rules.core.logger
import habapp_rules.energy.donut_chart

LOGGER = logging.getLogger(__name__)

MONTH_MAPPING = {
	1: "Januar",
	2: "Februar",
	3: "März",
	4: "April",
	5: "Mai",
	6: "Juni",
	7: "Juli",
	8: "August",
	9: "September",
	10: "Oktober",
	11: "November",
	12: "Dezember"
}


def _get_last_month_name() -> str:
	"""Get name of the current month

	:return: name of current month

	if other languages are required, the global dict must be replaced
	"""
	today = datetime.date.today()
	last_month = today.replace(day=1) - datetime.timedelta(days=1)

	return MONTH_MAPPING[last_month.month]


def _get_next_trigger() -> datetime.datetime:
	"""Get next trigger time (always first day of month at midnight)

	:return: next trigger time
	"""
	return datetime.datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) + dateutil.relativedelta.relativedelta(months=1)


@dataclasses.dataclass
class EnergyShare:
	"""Dataclass for defining energy share objects."""
	openhab_name: str
	chart_name: str
	monthly_power: float = 0

	_openhab_item = None

	def __post_init__(self) -> None:
		"""This is triggered after init.

		:raises habapp_rules.core.exceptions.HabAppRulesConfigurationException: if the number item could not be found
		"""
		try:
			self._openhab_item = HABApp.openhab.items.NumberItem.get_item(self.openhab_name)
		except AssertionError:
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"Could not find Number item for given name '{self.openhab_name}'")

	@property
	def openhab_item(self) -> HABApp.openhab.items.NumberItem:
		"""Get OpenHAB item.

		:return: OpenHAB item
		"""
		return self._openhab_item


class MonthlyReport(HABApp.Rule):

	def __init__(
			self,
			name_energy_sum,
			known_energy_share: list[EnergyShare],
			persistence_group_name: str | None,
			config_mail: multi_notifier.connectors.connector_mail.MailConfig | None,
			recipients: str | list[str]) -> None:
		HABApp.Rule.__init__(self)
		self._instance_logger = habapp_rules.core.logger.InstanceLogger(LOGGER, name_energy_sum)
		self._recipients = recipients

		self._item_energy_sum = HABApp.openhab.items.NumberItem.get_item(name_energy_sum)
		self._known_energy_share = known_energy_share
		self._mail = multi_notifier.connectors.connector_mail.Mail(config_mail)

		if persistence_group_name is not None:
			# check if all energy items are in the given persistence group
			items_to_check = [self._item_energy_sum] + [share.openhab_item for share in self._known_energy_share]
			not_in_persistence_group = [item.name for item in items_to_check if persistence_group_name not in item.groups]
			if not_in_persistence_group:
				raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"The following OpenHAB items are not in the persistence group '{persistence_group_name}': {not_in_persistence_group}")

		self.run.at(next_trigger_time := _get_next_trigger(), self._cb_send_energy)
		self._instance_logger.info(f"Successfully initiated monthly consumption rule for {name_energy_sum}. Triggered first execution to {next_trigger_time.isoformat()}")

		self._cb_send_energy()  # todo remove

	def _get_historic_value(self, item: HABApp.openhab.items.NumberItem, start_time: datetime.datetime) -> float:
		"""Get historic value of given Number item

		:param item: item instance
		:param start_time: start time to search for the interested value
		:return: historic value of the item
		"""
		historic = item.get_persistence_data(start_time=start_time, end_time=start_time + datetime.timedelta(hours=1)).data
		if not historic:
			self._instance_logger.warning(f"Could not get value of item '{item.name}' of time = {start_time}")
			return 0

		return next(iter(historic.values()))

	# pylint: disable=wrong-spelling-in-docstring
	def _create_html(self, energy_sum_month: float) -> str:
		"""Create html which will be sent by the mail

		:param energy_sum_month: sum value for the current month
		:return: html with replaced values

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
		"""
		html_template_path = pathlib.Path(__file__).parent / "monthly_report_template.html"

		with html_template_path.open() as html_template_file:
			html_template = html_template_file.read()

		return jinja2.Template(html_template).render(
			month=_get_last_month_name(),
			energy_now=f"{self._item_energy_sum.value:.1f}",
			energ_last_month=f"{energy_sum_month:.1f}",
			habapp_version=habapp_rules.__version__.__version__,
			chart="{{ chart }}"  # this is needed to not replace the chart from the mail-template
		)

	def _cb_send_energy(self) -> None:
		"""Send the mail with the energy consumption of the last month"""
		self._instance_logger.debug("Send energy consumption was triggered.")
		# get values
		now = datetime.datetime.now()
		last_month = now - dateutil.relativedelta.relativedelta(months=1)
		last_month = now - dateutil.relativedelta.relativedelta(days=1)  # todo remove

		energy_sum_month = self._item_energy_sum.value - self._get_historic_value(self._item_energy_sum, last_month)
		for share in self._known_energy_share:
			share.monthly_power = share.openhab_item.value - self._get_historic_value(share.openhab_item, last_month)

		energy_unknown = energy_sum_month - sum(share.monthly_power for share in self._known_energy_share)

		with tempfile.TemporaryDirectory() as temp_dir_name:
			# create plot
			labels = [share.chart_name for share in self._known_energy_share] + ["Rest"]
			values = [share.monthly_power for share in self._known_energy_share] + [energy_unknown]
			chart_path = pathlib.Path(temp_dir_name) / "chart.png"
			habapp_rules.energy.donut_chart.create_chart(labels, values, chart_path)

			# get html
			html = self._create_html(energy_sum_month)

			# send mail
			self._mail.send_message(self._recipients, html, f"Stromverbrauch {_get_last_month_name()}", images={"chart": str(chart_path)})

		self.run.at(next_trigger_time := _get_next_trigger(), self._cb_send_energy)
		self._instance_logger.info(f"Successfully sent energy consumption mail to {self._recipients}. Scheduled the next trigger time to {next_trigger_time.isoformat()}")
