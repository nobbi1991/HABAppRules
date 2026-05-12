"""Test config models of dwd rules."""

from HABApp.openhab.items import NumberItem, StringItem, SwitchItem

from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from habapp_rules.sensors.config.dwd import WindAlarmConfig, WindAlarmItems, WindAlarmParameter
from tests.helper.oh_item import (
    add_mock_item,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBase


class TestWindAlarmConfig(TestCaseBase):
    """Test WindAlarmConfig."""

    def setUp(self) -> None:
        """Set up Unittests."""
        super().setUp()
        add_mock_item(SwitchItem, "Unittest_Wind_Alarm", None)
        add_mock_item(SwitchItem, "Unittest_Manual", None)
        add_mock_item(NumberItem, "Unittest_Hand_Timeout", None)
        add_mock_item(StringItem, "H_Unittest_Wind_Alarm_state", None)

    def test_check_hand_timeout(self) -> None:
        """Test check_hand_timeout."""
        # no timeout is given
        with self.assertRaises(HabAppRulesConfigurationError):
            WindAlarmConfig(items=WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", state="H_Unittest_Wind_Alarm_state"))

        # only timeout item is given
        WindAlarmConfig(items=WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", hand_timeout="Unittest_Hand_Timeout", state="H_Unittest_Wind_Alarm_state"))

        # only timeout parameter is given
        WindAlarmConfig(items=WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", state="H_Unittest_Wind_Alarm_state"), parameter=WindAlarmParameter(hand_timeout=12 * 3600))

        # timeout parameter and item are given
        with self.assertRaises(HabAppRulesConfigurationError):
            WindAlarmConfig(
                items=WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", hand_timeout="Unittest_Hand_Timeout", state="H_Unittest_Wind_Alarm_state"),
                parameter=WindAlarmParameter(hand_timeout=12 * 3600),
            )

    def test_hand_timeout(self) -> None:
        """Test hand_timeout."""
        # Item is set, but value is None
        config = WindAlarmConfig(items=WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", hand_timeout="Unittest_Hand_Timeout", state="H_Unittest_Wind_Alarm_state"))
        self.assertEqual(config.hand_timeout, 24 * 3600)

        # Item is set and value is not None
        set_item_state("Unittest_Hand_Timeout", 1000)
        self.assertEqual(config.hand_timeout, 1000)

        # Parameter is set
        config = WindAlarmConfig(items=WindAlarmItems(wind_alarm="Unittest_Wind_Alarm", manual="Unittest_Manual", state="H_Unittest_Wind_Alarm_state"), parameter=WindAlarmParameter(hand_timeout=12 * 3600))
        self.assertEqual(config.hand_timeout, 12 * 3600)
