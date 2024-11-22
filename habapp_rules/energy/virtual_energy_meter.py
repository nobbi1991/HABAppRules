import HABApp

from habapp_rules.energy.config.virtual_energy_meter import EnergyMeterSwitchConfig


class VirtualEnergyMeterSwitch(HABApp.Rule):

	def __init__(self, config: EnergyMeterSwitchConfig) -> None:
		HABApp.Rule.__init__(self)
		self._config = config

		self._send_energy_countdown = self.run.countdown(self._get_energy_countdown_time(), self._cb_countdown_end)

		self._config.items.monitored_switch.listen_event(self._cb_switch, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _get_energy_countdown_time(self) -> float:
		# calc time to send every 10 W # todo set via config, or calculate it

		# E = P * t -> t = E / P -> t = 10W / P

		return 10 / self._config.parameter.power * 3600

	def _cb_switch(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:

		if self._config.items.power_output is not None:
			self._config.items.power_output.oh_send_command(self._config.parameter.power if event.value == "ON" else 0)

		if self._config.items.energy_output is not None:
			self._send_energy_countdown.reset()

			if event.value == "OFF":
				self._cb_switched_off()

	def _cb_countdown_end(self):
		self._update_energy_item(self._get_energy_countdown_time())
		self._send_energy_countdown.reset()

	def _cb_switched_off(self):
		self._update_energy_item(self._send_energy_countdown.remaining())
		self._send_energy_countdown.stop()

	def _update_energy_item(self, time: float):
		new_energy_value = self._config.items.energy_output.value + self._config.parameter.power * time
		self._config.items.energy_output.oh_send_command(new_energy_value)
