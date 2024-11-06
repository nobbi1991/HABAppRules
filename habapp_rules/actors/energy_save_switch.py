"""Energy save switch rules."""
import HABApp

import habapp_rules.actors.config.energy_save_switch
import habapp_rules.actors.state_observer
from habapp_rules.system import SleepState, PresenceState


class EnergySaveSwitch(HABApp.Rule):
	"""Rule for energy saving switch."""

	def __init__(self, config: habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchConfig) -> None:
		"""Initialize EnergySaveSwitch

		:param config: config for energy save switch
		"""
		HABApp.Rule.__init__(self)

		self._config = config
		self._switch_observer = habapp_rules.actors.state_observer.StateObserverSwitch(config.items.switch.name, self._cb_hand, self._cb_hand)

		# timer
		self._max_on_countdown = self.run.countdown(self._config.parameter.max_on_time, self._cb_countdown_end) if self._config.parameter.max_on_time is not None else None
		self._hand_countdown = self.run.countdown(self._config.parameter.hand_timeout, self._cb_countdown_end) if self._config.parameter.hand_timeout is not None else None

		# callbacks
		self._config.items.switch.listen_event(self._cb_switch, HABApp.openhab.events.ItemStateChangedEventFilter())

		if self._config.items.presence_state is not None:
			self._config.items.presence_state.listen_event(self._cb_presence_state, HABApp.openhab.events.ItemStateChangedEventFilter())
		if self._config.items.sleeping_state is not None:
			self._config.items.sleeping_state.listen_event(self._cb_sleeping_state, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _set_switch_state(self, target_state: bool) -> None:
		"""Set switch state if manual mode is not active.

		:param target_state: target state which should be set to the switch item
		"""
		if self._config.items.manual is not None and self._config.items.manual.is_on():
			return

		self._switch_observer.send_command("ON" if target_state else "OFF")

	def _stop_timers(self) -> None:
		"""Stop all timers / countdowns."""
		if self._max_on_countdown is not None and self._max_on_countdown.remaining():
			self._max_on_countdown.stop()
		if self._hand_countdown is not None and self._hand_countdown.remaining():
			self._hand_countdown.stop()

	def _cb_switch(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if switch changed.

		:param event: event which triggered this callback
		"""
		if event.value == "ON" and self._max_on_countdown is not None:
			self._max_on_countdown.reset()

		if event.value == "OFF":
			self._stop_timers()

	def _cb_hand(self, event: HABApp.openhab.events.ItemStateChangedEvent):
		"""Callback, which is triggered by the state observer if a manual change was detected

		:param event: event which triggered this callback.
		"""
		if event.value == "ON" and self._hand_countdown is not None:
			self._hand_countdown.reset()

	def _cb_presence_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if presence_state changed.

		:param event: event which triggered this callback
		"""
		if event.value == PresenceState.PRESENCE.value:
			self._set_switch_state(True)
		elif event.value == PresenceState.LEAVING.value:
			self._set_switch_state(False)

	def _cb_sleeping_state(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if sleeping state changed.

		:param event: event which triggered this callback
		"""
		if event.value == SleepState.AWAKE.value:
			self._set_switch_state(True)
		elif event.value == SleepState.PRE_SLEEPING.value:
			self._set_switch_state(False)

	def _cb_countdown_end(self):
		"""Callback, which is triggered if a countdown has ended."""
		if self._switch_observer.value:
			self._set_switch_state(False)


class EnergySaveSwitchWithCurrent(EnergySaveSwitch):
	"""EnergySaveSwitch with current measurement."""

	_config: habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchCurrentConfig

	def __init__(self, config: habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchCurrentConfig) -> None:
		"""Initialize EnergySaveSwitchWithCurrent

		:param config: energy save switch configuration
		"""
		EnergySaveSwitch.__init__(self, config)

		self._wait_for_current_below_threshold = False
		self._config.items.current.listen_event(self._cb_current_changed, HABApp.openhab.events.ItemStateChangedEventFilter())

	def _set_switch_state(self, target_state: bool) -> None:
		"""Set switch state if manual mode is not active.

		:param target_state: target state which should be set to the switch item
		"""
		if self._config.items.manual is not None and self._config.items.manual.is_on():
			return

		if target_state:
			self._switch_observer.send_command("ON")
		else:
			if self._config.items.current.value < self._config.parameter.current_threshold:
				self._switch_observer.send_command("OFF")
			else:
				self._wait_for_current_below_threshold = True

	def _cb_switch(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback which is triggered if switch changed.

		:param event: event, which triggered this callback
		"""
		self._wait_for_current_below_threshold = False
		super()._cb_switch(event)

	def _cb_current_changed(self, event: HABApp.openhab.events.ItemStateChangedEvent) -> None:
		"""Callback, which is triggered if the current value changed.

		:param event: event, which triggered this callback
		"""
		if self._wait_for_current_below_threshold and event.value < self._config.parameter.current_threshold:
			self._set_switch_state(False)
