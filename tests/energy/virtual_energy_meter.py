"""Test energy save switch rules."""

import collections
import unittest.mock

import HABApp.rule.rule

import habapp_rules.energy.config.virtual_energy_meter
import habapp_rules.energy.virtual_energy_meter
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.energy.config.virtual_energy_meter import PowerMapping


class TestVirtualEnergyMeterSwitch(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing VirtualEnergyMeterSwitch."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Switch")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Power_Dimmer")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Energy_Dimmer")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_only_Power")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_only_Energy")

        self._config_max = habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchConfig(
            items=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchItems(monitored_switch="Unittest_Switch", power_output="Unittest_Power_Dimmer", energy_output="Unittest_Energy_Dimmer"),
            parameter=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchParameter(power=100, energy_update_resolution=1),
        )

        self._config_only_power = habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchConfig(
            items=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchItems(monitored_switch="Unittest_Switch", power_output="Unittest_only_Power"),
            parameter=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchParameter(power=42),
        )

        self._config_only_energy = habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchConfig(
            items=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchItems(monitored_switch="Unittest_Switch", energy_output="Unittest_only_Energy"),
            parameter=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterSwitchParameter(power=10_000),
        )

        self._rule_max = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterSwitch(self._config_max)
        self._rule_only_power = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterSwitch(self._config_only_power)
        self._rule_only_energy = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterSwitch(self._config_only_energy)

    def test_init_with_switch_on(self) -> None:
        """Test init with switch on."""
        tests.helper.oh_item.item_state_change_event("Unittest_Switch", "ON")

        with unittest.mock.patch("HABApp.rule.scheduler.job_builder.HABAppJobBuilder.soon") as run_soon_mock:
            rule = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterSwitch(self._config_max)

        run_soon_mock.assert_called_once_with(rule._cb_monitored_item, unittest.mock.ANY)
        self.assertEqual("Unittest_Switch", run_soon_mock.call_args[0][1].name)
        self.assertEqual("ON", run_soon_mock.call_args[0][1].value)

    def test_get_power(self) -> None:
        """Test _get_power."""
        self.assertEqual(100, self._rule_max._get_power())
        self.assertEqual(42, self._rule_only_power._get_power())
        self.assertEqual(10_000, self._rule_only_energy._get_power())

    def test_get_energy_countdown_time(self) -> None:
        """Test _get_energy_countdown_time."""
        TestCase = collections.namedtuple("TestCase", "power, energy_update_resolution, expected_time")

        test_cases = [
            TestCase(power=10, energy_update_resolution=0.010, expected_time=3600),
            TestCase(power=10, energy_update_resolution=0.001, expected_time=360),
            TestCase(power=100, energy_update_resolution=0.010, expected_time=360),
            TestCase(power=100, energy_update_resolution=0.001, expected_time=36),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._rule_max._config.parameter.energy_update_resolution = test_case.energy_update_resolution
                self._rule_max._power = test_case.power
                self.assertEqual(test_case.expected_time, self._rule_max._get_energy_countdown_time())

    def test_power(self) -> None:
        """Test if power ist set correctly."""
        tests.helper.oh_item.assert_value("Unittest_Power_Dimmer", 0)
        tests.helper.oh_item.assert_value("Unittest_only_Power", 0)

        tests.helper.oh_item.item_state_change_event("Unittest_Switch", "ON")
        tests.helper.oh_item.assert_value("Unittest_Power_Dimmer", 100)
        tests.helper.oh_item.assert_value("Unittest_only_Power", 42)

        tests.helper.oh_item.item_state_change_event("Unittest_Switch", "OFF")
        tests.helper.oh_item.assert_value("Unittest_Power_Dimmer", 0)
        tests.helper.oh_item.assert_value("Unittest_only_Power", 0)

    def test_energy(self) -> None:
        """Test if energy ist set correctly."""
        tests.helper.oh_item.assert_value("Unittest_Energy_Dimmer", 0)
        tests.helper.oh_item.assert_value("Unittest_only_Energy", 0)

        tests.helper.oh_item.item_state_change_event("Unittest_Switch", "ON")
        tests.helper.oh_item.assert_value("Unittest_Energy_Dimmer", 0)
        tests.helper.oh_item.assert_value("Unittest_only_Energy", 0)

    def test_cb_monitored_item(self) -> None:
        """Test _cb_monitored_item."""
        with (
            unittest.mock.patch.object(self._rule_max, "_reset_countdown") as max_reset_countdown_mock,
            unittest.mock.patch.object(self._rule_max, "_set_energy_from_remaining_time") as max_set_energy_mock,
            unittest.mock.patch.object(self._rule_only_power, "_reset_countdown") as only_reset_countdown_mock,
            unittest.mock.patch.object(self._rule_only_power, "_set_energy_from_remaining_time") as only_set_energy_mock,
        ):
            # ON
            tests.helper.oh_item.item_state_change_event("Unittest_Switch", "ON")
            max_reset_countdown_mock.assert_called_once_with()
            max_set_energy_mock.assert_not_called()
            only_reset_countdown_mock.assert_not_called()
            only_set_energy_mock.assert_not_called()

            # OFF
            max_reset_countdown_mock.reset_mock()
            tests.helper.oh_item.item_state_change_event("Unittest_Switch", "OFF")
            max_reset_countdown_mock.assert_not_called()
            max_set_energy_mock.assert_called_once_with()
            only_reset_countdown_mock.assert_not_called()
            only_set_energy_mock.assert_not_called()

    def test_reset_countdown(self) -> None:
        """Test _reset_countdown."""
        with unittest.mock.patch.object(self._rule_max, "_send_energy_countdown") as countdown_mock, unittest.mock.patch.object(self._rule_max, "_get_energy_countdown_time") as get_time_mock, unittest.mock.patch("time.time", return_value=42):
            self._rule_max._reset_countdown()
            countdown_mock.set_countdown.assert_called_once_with(get_time_mock.return_value)
            countdown_mock.reset.assert_called_once()
            self.assertEqual(42, self._rule_max._last_energy_countdown_reset)

    def test_cb_countdown_end(self) -> None:
        """Test _cb_countdown_end."""
        with (
            unittest.mock.patch.object(self._rule_max, "_update_energy_item") as update_energy_item_mock,
            unittest.mock.patch.object(self._rule_max, "_get_energy_countdown_time") as get_countdown_mock,
            unittest.mock.patch.object(self._rule_max, "_reset_countdown") as reset_countdown_mock,
        ):
            self._rule_max._cb_countdown_end()
            update_energy_item_mock.assert_called_once_with(get_countdown_mock.return_value)
            reset_countdown_mock.assert_called_once()

    def test_update_energy_item(self) -> None:
        """Test _update_energy_item."""
        TestCase = collections.namedtuple("TestCase", "energy_output_value, power, time_since_last_update, expected_energy")

        test_cases = [
            TestCase(energy_output_value=0, power=0, time_since_last_update=0, expected_energy=0),
            TestCase(energy_output_value=0, power=0, time_since_last_update=10, expected_energy=0),
            TestCase(energy_output_value=0, power=100, time_since_last_update=0, expected_energy=0),
            TestCase(energy_output_value=0, power=100, time_since_last_update=10, expected_energy=0.1 * 10 / 3600),
            TestCase(energy_output_value=0, power=-100, time_since_last_update=0, expected_energy=0),
            TestCase(energy_output_value=0, power=-100, time_since_last_update=10, expected_energy=-0.1 * 10 / 3600),
            # with initial power
            TestCase(energy_output_value=1000, power=0, time_since_last_update=0, expected_energy=1000),
            TestCase(energy_output_value=1000, power=0, time_since_last_update=10, expected_energy=1000),
            TestCase(energy_output_value=1000, power=100, time_since_last_update=0, expected_energy=1000),
            TestCase(energy_output_value=1000, power=100, time_since_last_update=10, expected_energy=1000 + 0.1 * 10 / 3600),
            TestCase(energy_output_value=1000, power=-100, time_since_last_update=0, expected_energy=1000),
            TestCase(energy_output_value=1000, power=-100, time_since_last_update=10, expected_energy=1000 - 0.1 * 10 / 3600),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._rule_max._config.items.energy_output.value = test_case.energy_output_value
                self._rule_max._power = test_case.power
                self._rule_max._update_energy_item(test_case.time_since_last_update)
                self.assertEqual(test_case.expected_energy, self._rule_max._config.items.energy_output.value)


class TestVirtualEnergyMeterNumber(tests.helper.test_case_base.TestCaseBase):
    """Tests cases for testing VirtualEnergyMeterNumber."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Dimmer")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Number")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Power_Dimmer")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Energy_Dimmer")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Power_Number")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Energy_Number")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_only_Power")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_only_Energy")

        self._config_max_dimmer = habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberConfig(
            items=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberItems(monitored_item="Unittest_Dimmer", power_output="Unittest_Power_Dimmer", energy_output="Unittest_Energy_Dimmer"),
            parameter=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberParameter(power_mapping=[PowerMapping(0, 0), PowerMapping(100, 1000)], energy_update_resolution=1),
        )

        self._config_max_number = habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberConfig(
            items=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberItems(monitored_item="Unittest_Number", power_output="Unittest_Power_Number", energy_output="Unittest_Energy_Number"),
            parameter=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberParameter(power_mapping=[PowerMapping(0, 0), PowerMapping(2, 100)], energy_update_resolution=1),
        )

        self._config_only_power = habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberConfig(
            items=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberItems(monitored_item="Unittest_Dimmer", power_output="Unittest_only_Power"),
            parameter=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberParameter(power_mapping=[PowerMapping(0, 0), PowerMapping(100, 42)]),
        )

        self._config_only_energy = habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberConfig(
            items=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberItems(monitored_item="Unittest_Dimmer", energy_output="Unittest_only_Energy"),
            parameter=habapp_rules.energy.config.virtual_energy_meter.EnergyMeterNumberParameter(power_mapping=[PowerMapping(0, 0), PowerMapping(100, 10_000)]),
        )

        self._rule_max_dimmer = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterNumber(self._config_max_dimmer)
        self._rule_max_number = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterNumber(self._config_max_number)
        self._rule_only_power = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterNumber(self._config_only_power)
        self._rule_only_energy = habapp_rules.energy.virtual_energy_meter.VirtualEnergyMeterNumber(self._config_only_energy)

    def test_power(self) -> None:
        """Test if power ist set correctly."""
        tests.helper.oh_item.assert_value("Unittest_Power_Dimmer", 0)
        tests.helper.oh_item.assert_value("Unittest_only_Power", 0)

        tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 100)
        tests.helper.oh_item.assert_value("Unittest_Power_Dimmer", 1000)
        tests.helper.oh_item.assert_value("Unittest_only_Power", 42)

        tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 50)
        tests.helper.oh_item.assert_value("Unittest_Power_Dimmer", 500)
        tests.helper.oh_item.assert_value("Unittest_only_Power", 21)

        tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 0)
        tests.helper.oh_item.assert_value("Unittest_Power_Dimmer", 0)
        tests.helper.oh_item.assert_value("Unittest_only_Power", 0)

    def test_get_energy_countdown_time(self) -> None:
        """Test _get_energy_countdown_time."""
        # power is not yet set -> avoid division by zero and return 1
        self.assertEqual(0, self._rule_max_dimmer._power)
        self.assertEqual(1, self._rule_max_dimmer._get_energy_countdown_time())

    def test_cb_monitored_item(self) -> None:
        """Test _cb_monitored_item."""
        with (
            unittest.mock.patch.object(self._rule_max_dimmer, "_reset_countdown") as max_reset_countdown_mock,
            unittest.mock.patch.object(self._rule_max_dimmer, "_set_energy_from_remaining_time") as max_set_energy_mock,
            unittest.mock.patch.object(self._rule_only_power, "_reset_countdown") as only_reset_countdown_mock,
            unittest.mock.patch.object(self._rule_only_power, "_set_energy_from_remaining_time") as only_set_energy_mock,
        ):
            # ON
            tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 20, 0)
            max_reset_countdown_mock.assert_called_once_with()
            max_set_energy_mock.assert_not_called()
            only_reset_countdown_mock.assert_not_called()
            only_set_energy_mock.assert_not_called()

            # Change
            max_reset_countdown_mock.reset_mock()
            tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 40, 0)
            max_reset_countdown_mock.assert_called_once_with()
            max_set_energy_mock.assert_called_once_with()
            only_reset_countdown_mock.assert_not_called()
            only_set_energy_mock.assert_not_called()

            # OFF
            max_reset_countdown_mock.reset_mock()
            max_set_energy_mock.reset_mock()
            tests.helper.oh_item.item_state_change_event("Unittest_Dimmer", 0, 20)
            max_reset_countdown_mock.assert_not_called()
            max_set_energy_mock.assert_called_once_with()
            only_reset_countdown_mock.assert_not_called()
            only_set_energy_mock.assert_not_called()
