import HABApp
import HABApp.core

import habapp_rules.system.config.low_battery
from habapp_rules.core.helper import send_if_different


class LowBattery(HABApp.Rule):
    def __init__(self, config: habapp_rules.system.config.low_battery.LowBatteryConfig):
        HABApp.Rule.__init__(self)
        self._config = config

        self._battery_items: list[HABApp.openhab.items.NumberItem] = []
        self.run.at(self.run.trigger.interval(0.1, self._config.parameter.update_items_time), self._update_battery_items)
        self.run.at(self.run.trigger.interval(0.5, self._config.parameter.check_values_time), self._check_battery_values)

    def _update_battery_items(self) -> None:
        self._battery_items = [itm for itm in HABApp.core.Items.get_items() if "bat" in itm.name and isinstance(itm, HABApp.openhab.items.NumberItem)]

    def _check_battery_values(self):
        low_batteries = [itm for itm in self._battery_items if itm.value < self._config.parameter.low_battery_threshold]

        warning_value = "ON" if low_batteries else "OFF"
        send_if_different(self._config.items.warning_low_battery, warning_value)
