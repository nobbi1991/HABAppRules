import dataclasses
import datetime
import pathlib

import HABApp
import dateutil.relativedelta
import matplotlib.pyplot
import multi_notifier.connectors.connector_mail

import habapp_rules.core.exceptions


@dataclasses.dataclass
class EnergyShare:
	openhab_name: str
	chart_name: str
	monthly_power: float = 0

	_openhab_item = None

	def __post_init__(self):
		try:
			self._openhab_item = HABApp.openhab.items.NumberItem.get_item(self.openhab_name)
		except AssertionError:
			raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"Could not find Number item for given name '{self.openhab_name}'")

	@property
	def openhab_item(self) -> HABApp.openhab.items.NumberItem:
		return self._openhab_item


@dataclasses.dataclass  # todo move to core? or add to multi_notifier as pydantic model
class MailConfig:
	user: str
	password: str
	smtp_host: str
	smtp_port: int


class MonthlyReport(HABApp.Rule):

	def __init__(self, name_energy_sum, known_energy_share: list[EnergyShare], persistence_group_name: str | None, config_mail: MailConfig | None = None) -> None:  # todo add telegram config
		HABApp.Rule.__init__(self)

		self._item_energy_sum = HABApp.openhab.items.NumberItem.get_item(name_energy_sum)
		self._known_energy_share = known_energy_share
		self._mail = multi_notifier.connectors.connector_mail.Mail(config_mail.user, config_mail.password, config_mail.smtp_host, config_mail.smtp_port)

		if persistence_group_name is not None:
			# check if all energy items are in the given persistence group
			items_to_check = [self._item_energy_sum] + [share.openhab_item for share in self._known_energy_share]
			not_in_persistence_group = [item.name for item in items_to_check if persistence_group_name not in item.groups]
			if not_in_persistence_group:
				raise habapp_rules.core.exceptions.HabAppRulesConfigurationException(f"The following OpenHAB items are not in the persistence group '{persistence_group_name}': {not_in_persistence_group}")

		self._send_energy()

	def _get_historic_value(self, item: HABApp.openhab.items.NumberItem, start_time: datetime.datetime) -> float:
		historic = item.get_persistence_data(start_time=start_time, end_time=start_time + datetime.timedelta(hours=1)).data  # todo check if there is data
		timestamp, value = next(iter(historic.items()))
		return value

	def _send_energy(self):
		# get values
		now = datetime.datetime.now()
		last_month = now - dateutil.relativedelta.relativedelta(months=1)

		energy_sum_month = self._get_historic_value(self._item_energy_sum, last_month)
		for share in self._known_energy_share:
			share.monthly_power = self._get_historic_value(share.openhab_item, last_month)

		energy_unknown = energy_sum_month - sum(share.monthly_power for share in self._known_energy_share)

		# create plot
		labels = [share.chart_name for share in self._known_energy_share] + ["Rest"]
		values = [share.monthly_power for share in self._known_energy_share] + [energy_unknown]

		fig, ax = matplotlib.pyplot.subplots()
		ax.pie(values, labels=labels, autopct='%1.1f kWh', pctdistance=0.7, textprops={'fontsize': 10})
		matplotlib.pyplot.savefig("chart.svg", bbox_inches="tight", transparent=True)

		# send mail
		html_template_path = pathlib.Path("montly_report_template.html")

		with html_template_path.open() as html_template_file:
			html = html_template_file.read()

		self._mail.send_message("norbert@seuling.eu", html, "Zählerstand")
