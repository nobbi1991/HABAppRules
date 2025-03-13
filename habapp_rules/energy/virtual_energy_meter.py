import abc
import time

import HABApp

from habapp_rules.energy.config.virtual_energy_meter import EnergyMeterNumberConfig, EnergyMeterSwitchConfig


class _VirtualEnergyMeterBase(HABApp.Rule):
    """Base class for virtual energy meter classes."""

    def __init__(self, config: EnergyMeterSwitchConfig | EnergyMeterNumberConfig) -> None:
        HABApp.Rule.__init__(self)
        self._config = config
        self._monitored_item = config.items.monitored_switch if isinstance(config, EnergyMeterSwitchConfig) else config.items.monitored_item

        if self._config.items.energy_output is not None and self._config.items.energy_output.value is None:
            self._config.items.energy_output.oh_send_command(0)

        self._power = self._get_power()
        self._last_energy_countdown_reset = 0
        self._send_energy_countdown = self.run.countdown(self._get_energy_countdown_time(), self._cb_countdown_end)
        self._monitored_item.listen_event(self._cb_monitored_item, HABApp.openhab.events.ItemStateChangedEventFilter())

        if self._is_on():
            self.run.soon(self._cb_monitored_item, HABApp.openhab.events.ItemStateChangedEvent(self._monitored_item.name, self._monitored_item.value, None))

        if self._config.items.power_output is not None:
            self._config.items.power_output.oh_send_command(self._get_power() if self._is_on() else 0)

    @abc.abstractmethod
    def _get_power(self) -> float:
        """Get power for monitored, for ON state.

        Returns:
            power
        """

    @abc.abstractmethod
    def _is_on(self) -> bool:
        """Check if monitored item is on.

        Returns:
            True if monitored item is on
        """

    def _get_energy_countdown_time(self) -> float:
        """Get time to send energy.

        Returns:
            time to send energy in seconds
        """
        # calc time to send every X W (X from config)
        # E = P * t -> t = E / P -> t = E / P
        if self._power == 0:
            return 1  # avoid divide by zero

        return self._config.parameter.energy_update_resolution / self._power * 3_600_000

    def _cb_monitored_item(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:  # noqa:  ARG002
        """Callback which is triggered if the monitored item changed.

        Args:
            event: event which triggered this callback
        """
        if self._is_on():
            self._power = self._get_power()

        if self._config.items.power_output is not None:
            self._config.items.power_output.oh_send_command(self._power if self._is_on() else 0)

    def _reset_countdown(self) -> None:
        """Reset countdown for sending energy."""
        self._send_energy_countdown.set_countdown(self._get_energy_countdown_time())
        self._send_energy_countdown.reset()
        self._last_energy_countdown_reset = time.time()

    def _cb_countdown_end(self) -> None:
        """Callback which is triggered if _send_energy_countdown ended."""
        self._update_energy_item(self._get_energy_countdown_time())
        self._reset_countdown()

    def _set_energy_from_remaining_time(self) -> None:
        """Callback which is triggered if switch / dimmer was switched off."""
        remaining_time = time.time() - self._last_energy_countdown_reset
        self._update_energy_item(remaining_time)
        self._send_energy_countdown.stop()

    def _update_energy_item(self, time_since_last_update: float) -> None:
        """Update energy item.

        Args:
            time_since_last_update: time since last update
        """
        new_energy_value = self._config.items.energy_output.value + self._power * time_since_last_update / 3_600_000
        self._config.items.energy_output.oh_send_command(new_energy_value)


class VirtualEnergyMeterSwitch(_VirtualEnergyMeterBase):
    """Rule to monitor energy consumption of switch items without a real energy meter.

    # Config
    config = VirtualEnergyMeterSwitch(config=EnergyMeterSwitchConfig(
        items=EnergyMeterSwitchItems(
            monitored_item="Switch",
            power_output="Virtual_Power",
            energy_output="Virtual_Energy"

        ),
        parameter=EnergyMeterSwitchParameter(
            power=42
        )
    ))

    # Rule init
    VirtualEnergyMeterSwitch(config)
    """

    def __init__(self, config: EnergyMeterSwitchConfig) -> None:
        """Init Rule.

        Args:
            config: Config for virtual energy meter
        """
        _VirtualEnergyMeterBase.__init__(self, config)

    def _get_power(self) -> float:
        """Get power for monitored, for ON state.

        Returns:
            power
        """
        return self._config.parameter.power

    def _is_on(self) -> bool:
        """Check if monitored item is on.

        Returns:
            True if monitored item is on
        """
        return self._monitored_item.is_on()

    def _cb_monitored_item(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if the monitored item changed.

        Args:
            event: event which triggered this callback
        """
        super()._cb_monitored_item(event)

        if self._config.items.energy_output is not None:
            if event.value == "ON":
                self._reset_countdown()
            else:
                self._set_energy_from_remaining_time()


class VirtualEnergyMeterNumber(_VirtualEnergyMeterBase):
    """Rule to monitor energy consumption of dimmer / number items without a real energy meter.

    # Config
    config = VirtualEnergyMeterNumber(config=EnergyMeterNumberConfig(
        items=EnergyMeterNumberItems(
            monitored_item="Dimmer",
            power_output="Virtual_Power",
            energy_output="Virtual_Energy"

        ),
        parameter=EnergyMeterNumberParameter(
            power_mapping=[
                PowerMapping(value=0, power=0),
                PowerMapping(value=100, power=10_000)
            ]
        )
    ))

    # Rule init
    VirtualEnergyMeterNumber(config)
    """

    def __init__(self, config: EnergyMeterNumberConfig) -> None:
        """Init Rule.

        Args:
            config: Config for virtual energy meter
        """
        if config.items.monitored_item.value is None:
            config.items.monitored_item.oh_send_command(0)

        _VirtualEnergyMeterBase.__init__(self, config)

    def _get_power(self) -> float:
        """Get power for monitored, for ON state.

        Returns:
            power
        """
        return self._config.parameter.get_power(self._config.items.monitored_item.value)

    def _is_on(self) -> bool:
        """Check if monitored item is on.

        Returns:
            True if monitored item is on
        """
        return self._get_power() != 0

    def _cb_monitored_item(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
        """Callback which is triggered if the monitored item changed.

        Args:
            event: event which triggered this callback
        """
        super()._cb_monitored_item(event)

        if self._config.items.energy_output is not None:
            if not event.value or (event.value and event.old_value):
                # switch off or value changed
                self._set_energy_from_remaining_time()

            if event.value:
                # switch on or value changed
                self._reset_countdown()
