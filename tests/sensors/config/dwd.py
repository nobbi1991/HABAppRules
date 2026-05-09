"""Test config models of dwd rules."""

import HABApp

import habapp_rules.core.exceptions
import habapp_rules.sensors.config.dwd
import tests.helper.oh_item
import tests.helper.test_case_base


class TestWindAlarmConfig(tests.helper.test_case_base.TestCaseBase):
    """Test WindAlarmConfig."""

    def setUp(self) -> None:
        """Set up Unittests."""
        super().setUp()
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Wind_Alarm", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Manual", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Hand_Timeout", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Wind_Alarm_state", None)

    def test_check_hand_timeout(self) -> None:
        """Test check_hand_timeout."""
        # no timeout is given
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.sensors.config.dwd.WindAlarmConfig(items=habapp_rules.sensors.config.dwd.WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", state="H_Unittest_Wind_Alarm_state"))

        # only timeout item is given
        habapp_rules.sensors.config.dwd.WindAlarmConfig(items=habapp_rules.sensors.config.dwd.WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", hand_timeout="Unittest_Hand_Timeout", state="H_Unittest_Wind_Alarm_state"))

        # only timeout parameter is given
        habapp_rules.sensors.config.dwd.WindAlarmConfig(
            items=habapp_rules.sensors.config.dwd.WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", state="H_Unittest_Wind_Alarm_state"), parameter=habapp_rules.sensors.config.dwd.WindAlarmParameter(hand_timeout=12 * 3600)
        )

        # timeout parameter and item are given
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.sensors.config.dwd.WindAlarmConfig(
                items=habapp_rules.sensors.config.dwd.WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", hand_timeout="Unittest_Hand_Timeout", state="H_Unittest_Wind_Alarm_state"),
                parameter=habapp_rules.sensors.config.dwd.WindAlarmParameter(hand_timeout=12 * 3600),
            )

    def test_hand_timeout(self) -> None:
        """Test hand_timeout."""
        # Item is set, but value is None
        config = habapp_rules.sensors.config.dwd.WindAlarmConfig(
            items=habapp_rules.sensors.config.dwd.WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", hand_timeout="Unittest_Hand_Timeout", state="H_Unittest_Wind_Alarm_state")
        )
        self.assertEqual(config.hand_timeout, 24 * 3600)

        # Item is set and value is not None
        tests.helper.oh_item.set_state("Unittest_Hand_Timeout", 1000)
        self.assertEqual(config.hand_timeout, 1000)

        # Parameter is set
        config = habapp_rules.sensors.config.dwd.WindAlarmConfig(
            items=habapp_rules.sensors.config.dwd.WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", state="H_Unittest_Wind_Alarm_state"), parameter=habapp_rules.sensors.config.dwd.WindAlarmParameter(hand_timeout=12 * 3600)
        )
        self.assertEqual(config.hand_timeout, 12 * 3600)
