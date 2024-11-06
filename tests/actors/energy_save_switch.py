"""Test energy save switch rules."""
import collections
import unittest.mock

import HABApp
import eascheduler.jobs.job_countdown

import habapp_rules.actors.config.energy_save_switch
import habapp_rules.actors.energy_save_switch
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.system import PresenceState, SleepState


# pylint: disable=protected-access, no-member
class TestEnergySaveSwitch(tests.helper.test_case_base.TestCaseBase):
	"""Test EnergySaveSwitch """

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_min")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_max")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch_manual")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state")

		self._config_min = habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchConfig(
			items=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchItems(
				switch="Unittest_Switch_min"
			)
		)

		self._config_max = habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchConfig(
			items=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchItems(
				switch="Unittest_Switch_max",
				manual="Unittest_Switch_manual",
				presence_state="Unittest_Presence_state",
				sleeping_state="Unittest_Sleep_state"
			),
			parameter=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchParameter(
				max_on_time=3600,
				hand_timeout=1800

			)

		)

		self._rule_min = habapp_rules.actors.energy_save_switch.EnergySaveSwitch(self._config_min)
		self._rule_max = habapp_rules.actors.energy_save_switch.EnergySaveSwitch(self._config_max)

	def test_init(self):
		"""Test __init__."""
		self.assertIsNone(self._rule_min._max_on_countdown)
		self.assertIsNone(self._rule_min._hand_countdown)

		self.assertIsInstance(self._rule_max._max_on_countdown, eascheduler.jobs.job_countdown.CountdownJob)
		self.assertIsInstance(self._rule_max._hand_countdown, eascheduler.jobs.job_countdown.CountdownJob)
		self.assertIsNone(self._rule_max._max_on_countdown.remaining())
		self.assertIsNone(self._rule_max._hand_countdown.remaining())

	def test_set_switch_state(self):
		"""Test set_switch_state."""
		# min rule
		with unittest.mock.patch.object(self._rule_min._switch_observer, "send_command") as send_command_min_mock:
			self._rule_min._set_switch_state(True)
			send_command_min_mock.assert_called_once_with("ON")
			self._rule_min._set_switch_state(False)
			send_command_min_mock.assert_called_with("OFF")

		# max rule | manual off
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_manual", "OFF")
		with unittest.mock.patch.object(self._rule_max._switch_observer, "send_command") as send_command_max_mock:
			self._rule_max._set_switch_state(True)
			send_command_max_mock.assert_called_once_with("ON")
			self._rule_max._set_switch_state(False)
			send_command_max_mock.assert_called_with("OFF")

		# max rule | manual on
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_manual", "ON")
		with unittest.mock.patch.object(self._rule_max._switch_observer, "send_command") as send_command_max_mock:
			self._rule_max._set_switch_state(True)
			send_command_max_mock.assert_not_called()
			self._rule_max._set_switch_state(False)
			send_command_max_mock.assert_not_called()

	def test_hand_state(self):
		"""Test hand state."""

		# hand on
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_min", "ON")
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_max", "ON")

		self.assertIsNone(self._rule_min._max_on_countdown)
		self.assertIsNone(self._rule_min._hand_countdown)

		self.assertGreater(self._rule_max._max_on_countdown.remaining().seconds, 3590)
		self.assertGreater(self._rule_max._hand_countdown.remaining().seconds, 1790)

		# hand off
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_min", "OFF")
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_max", "OFF")

		self.assertIsNone(self._rule_min._max_on_countdown)
		self.assertIsNone(self._rule_min._hand_countdown)

		self.assertIsNone(self._rule_max._max_on_countdown.remaining())
		self.assertIsNone(self._rule_max._hand_countdown.remaining())

	def test_presence_state(self):
		"""Test presence state."""

		TestCase = collections.namedtuple("TestCase", "state, min_value, max_value")

		test_cases = [
			TestCase(PresenceState.PRESENCE.value, None, "ON"),
			TestCase(PresenceState.LEAVING.value, None, "OFF"),
			TestCase(PresenceState.ABSENCE.value, None, "OFF"),
			TestCase(PresenceState.LONG_ABSENCE.value, None, "OFF"),
		]

		# manual on
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_manual", "ON")
		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", test_case.state)
				tests.helper.oh_item.assert_value("Unittest_Switch_min", None)
				tests.helper.oh_item.assert_value("Unittest_Switch_max", None)
				self.assertIsNone(self._rule_max._max_on_countdown.remaining())

		# manual off
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_manual", "OFF")
		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				tests.helper.oh_item.item_state_change_event("Unittest_Presence_state", test_case.state)
				tests.helper.oh_item.assert_value("Unittest_Switch_min", test_case.min_value)
				tests.helper.oh_item.assert_value("Unittest_Switch_max", test_case.max_value)
				self.assertIsNone(self._rule_max._hand_countdown.remaining())

				if test_case.max_value == "ON":
					self.assertGreater(self._rule_max._max_on_countdown.remaining().seconds, 3590)
				else:
					self.assertIsNone(self._rule_max._max_on_countdown.remaining())

	def test_sleeping_state(self):
		"""Test sleeping state."""
		TestCase = collections.namedtuple("TestCase", "state, min_value, max_value")

		test_cases = [
			TestCase(SleepState.PRE_SLEEPING.value, None, "OFF"),
			TestCase(SleepState.SLEEPING.value, None, "OFF"),
			TestCase(SleepState.POST_SLEEPING.value, None, "OFF"),
			TestCase(SleepState.AWAKE.value, None, "ON"),
		]

		# manual on
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_manual", "ON")
		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", test_case.state)
				tests.helper.oh_item.assert_value("Unittest_Switch_min", None)
				tests.helper.oh_item.assert_value("Unittest_Switch_max", None)
				self.assertIsNone(self._rule_max._max_on_countdown.remaining())

		# manual off
		tests.helper.oh_item.item_state_change_event("Unittest_Switch_manual", "OFF")
		for test_case in test_cases:
			with self.subTest(test_case=test_case):
				tests.helper.oh_item.item_state_change_event("Unittest_Sleep_state", test_case.state)
				tests.helper.oh_item.assert_value("Unittest_Switch_min", test_case.min_value)
				tests.helper.oh_item.assert_value("Unittest_Switch_max", test_case.max_value)
				self.assertIsNone(self._rule_max._hand_countdown.remaining())

				if test_case.max_value == "ON":
					self.assertGreater(self._rule_max._max_on_countdown.remaining().seconds, 3590)
				else:
					self.assertIsNone(self._rule_max._max_on_countdown.remaining())

	def test_cb_end(self):
		"""Test cb_end."""
		with unittest.mock.patch.object(self._rule_max, "_stop_timers") as stop_timers_mock:
			# None
			tests.helper.oh_item.item_state_change_event("Unittest_Switch_max", "OFF")
			self._rule_max._cb_countdown_end()
			tests.helper.oh_item.assert_value("Unittest_Switch_max", "OFF")
			stop_timers_mock.assert_called_once()

			# on
			stop_timers_mock.reset_mock()
			tests.helper.oh_item.item_state_change_event("Unittest_Switch_max", "ON")
			self._rule_max._cb_countdown_end()
			tests.helper.oh_item.assert_value("Unittest_Switch_max", "OFF")
			stop_timers_mock.assert_called_once()

			# off
			stop_timers_mock.reset_mock()
			tests.helper.oh_item.item_state_change_event("Unittest_Switch_max", "OFF")
			self._rule_max._cb_countdown_end()
			tests.helper.oh_item.assert_value("Unittest_Switch_max", "OFF")
			stop_timers_mock.assert_called_once()


class TestEnergySaveSwitchCurrent(tests.helper.test_case_base.TestCaseBase):
	"""Test EnergySaveSwitchCurrent rule."""

	def setUp(self) -> None:
		"""Setup test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Current")

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Presence_state")
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_Sleep_state")

		self._config = habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchCurrentConfig(
			items=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchCurrentItems(
				switch="Unittest_Switch",
				manual="Unittest_Manual",
				current="Unittest_Current",
				presence_state="Unittest_Presence_state",
				sleeping_state="Unittest_Sleep_state"
			),
			parameter=habapp_rules.actors.config.energy_save_switch.EnergySaveSwitchCurrentParameter(
				max_on_time=3600,
				hand_timeout=1800,
				current_threshold=0.5
			)
		)

		self._rule = habapp_rules.actors.energy_save_switch.EnergySaveSwitchWithCurrent(self._config)

	def test_hand(self):
		"""Test hand commands."""
		# hand on
		tests.helper.oh_item.item_state_change_event("Unittest_Switch", "ON")
		self.assertFalse(self._rule._wait_for_current_below_threshold)
		tests.helper.oh_item.item_state_change_event("Unittest_Current", 2)
		self.assertFalse(self._rule._wait_for_current_below_threshold)

		# hand off
		tests.helper.oh_item.item_state_change_event("Unittest_Switch", "OFF")
		self.assertFalse(self._rule._wait_for_current_below_threshold)
		tests.helper.oh_item.item_state_change_event("Unittest_Current", 0)
		self.assertFalse(self._rule._wait_for_current_below_threshold)

	def test_switch_off_by_current(self):
		"""Test switch off by current."""
		# trigger ON from sleeping or presence
		self._rule._set_switch_state(True)
		tests.helper.oh_item.assert_value("Unittest_Switch", "ON")
		self.assertFalse(self._rule._wait_for_current_below_threshold)
		tests.helper.oh_item.item_state_change_event("Unittest_Current", 2)

		# trigger OFF from sleeping or presence
		self._rule._set_switch_state(False)
		tests.helper.oh_item.assert_value("Unittest_Switch", "ON")
		self.assertTrue(self._rule._wait_for_current_below_threshold)

		# some random current above values
		tests.helper.oh_item.item_state_change_event("Unittest_Current", 7)
		tests.helper.oh_item.item_state_change_event("Unittest_Current", 1.2)
		tests.helper.oh_item.item_state_change_event("Unittest_Current", 0.6)
		tests.helper.oh_item.assert_value("Unittest_Switch", "ON")
		self.assertTrue(self._rule._wait_for_current_below_threshold)

		# current value below threshold
		tests.helper.oh_item.item_state_change_event("Unittest_Current", 0.4)
		tests.helper.oh_item.assert_value("Unittest_Switch", "OFF")
		self.assertFalse(self._rule._wait_for_current_below_threshold)

		# switch ON
		self._rule._set_switch_state(True)
		tests.helper.oh_item.assert_value("Unittest_Switch", "ON")

		# switch OFF (current already below threshold)
		self._rule._set_switch_state(False)
		tests.helper.oh_item.assert_value("Unittest_Switch", "OFF")

	def test_no_switching_when_manual(self):
		"""Test no switching when manual."""
		tests.helper.oh_item.item_state_change_event("Unittest_Current", 0)
		tests.helper.oh_item.item_state_change_event("Unittest_Manual", "ON")

		# switch ON
		self._rule._set_switch_state(True)
		tests.helper.oh_item.assert_value("Unittest_Switch", None)

		# switch OFF (current already below threshold)
		self._rule._set_switch_state(False)
		tests.helper.oh_item.assert_value("Unittest_Switch", None)
