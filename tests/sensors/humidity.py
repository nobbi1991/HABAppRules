"""Tests for motion sensors."""

import collections
import sys
import unittest
import unittest.mock

from HABApp.openhab.items import NumberItem, StringItem, SwitchItem

from habapp_rules.sensors.config.humidity import HumiditySwitchConfig, HumiditySwitchItems, HumiditySwitchParameter
from habapp_rules.sensors.humidity import HumiditySwitch
from tests.helper.graph_machines import create_state_graphs
from tests.helper.oh_item import (
    add_mock_item,
    assert_item_value,
    item_state_event,
    set_item_state,
)
from tests.helper.test_case_base import TestCaseBaseStateMachine
from tests.helper.timer import call_timeout


class TestMotion(TestCaseBaseStateMachine):
    """Tests cases for testing motion sensors rule."""

    def setUp(self) -> None:
        """Setup test case."""
        super().setUp()

        add_mock_item(NumberItem, "Unittest_Humidity", None)
        add_mock_item(SwitchItem, "Unittest_Output", None)
        add_mock_item(StringItem, "H_Unittest_Output_state", None)
        add_mock_item(StringItem, "Custom_Name", None)

        config = HumiditySwitchConfig(items=HumiditySwitchItems(humidity="Unittest_Humidity", output="Unittest_Output", state="H_Unittest_Output_state"))

        self.humidity = HumiditySwitch(config)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        create_state_graphs(self.humidity, "Humidity")

    def test_init(self) -> None:
        """Test init."""
        full_config = HumiditySwitchConfig(
            items=HumiditySwitchItems(humidity="Unittest_Humidity", output="Unittest_Output", state="Custom_Name"),
            parameter=HumiditySwitchParameter(absolute_threshold=70, extended_time=42),
        )

        humidity = HumiditySwitch(full_config)
        self.assertEqual(70, humidity._config.parameter.absolute_threshold)
        self.assertEqual(42, humidity.state_machine.get_state("on_Extended").timeout)
        self.assertEqual("Custom_Name", humidity._item_state.name)

    def test_get_initial_state(self) -> None:
        """Test get_initial_state."""
        TestCase = collections.namedtuple("TestCase", "humidity_value, expected_state")

        test_cases = [
            TestCase(None, "off"),
            TestCase(64, "off"),
            TestCase(65, "on"),
            TestCase(66, "on"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("Unittest_Humidity", test_case.humidity_value)
                self.assertEqual(test_case.expected_state, self.humidity._get_initial_state())

    def test_check_high_humidity(self) -> None:
        """Test check_high_humidity."""
        TestCase = collections.namedtuple("TestCase", "item_value,given_value, expected_result")

        test_cases = [
            # False | False -> False
            TestCase(None, None, False),
            TestCase(None, 64, False),
            TestCase(64, None, False),
            TestCase(64, 64, False),
            # False | True -> True
            TestCase(None, 65, True),
            TestCase(64, 65, True),
            # True | False -> False
            TestCase(65, None, True),
            TestCase(65, 64, False),
            # True | True -> True
            TestCase(65, 65, True),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                set_item_state("Unittest_Humidity", test_case.item_value)
                self.assertEqual(test_case.expected_result, self.humidity._check_high_humidity(test_case.given_value))

    def test_cb_humidity(self) -> None:
        """Test _cb_humidity."""
        with (
            unittest.mock.patch.object(self.humidity, "trigger") as trigger_mock,
            unittest.mock.patch.object(self.humidity, "_check_high_humidity", return_value=True) as check_mock,
        ):
            item_state_event("Unittest_Humidity", 99)
            check_mock.assert_called_once_with(99)
            trigger_mock.assert_called_once_with("high_humidity_start")

        with (
            unittest.mock.patch.object(self.humidity, "trigger") as trigger_mock,
            unittest.mock.patch.object(self.humidity, "_check_high_humidity", return_value=False) as check_mock,
        ):
            item_state_event("Unittest_Humidity", 42)
            check_mock.assert_called_once_with(42)
            trigger_mock.assert_called_once_with("high_humidity_end")

    def test_states(self) -> None:
        """Test states."""
        self.assertEqual("off", self.humidity.state)

        # some humidity changes below threshold
        item_state_event("Unittest_Humidity", 64)
        self.assertEqual("off", self.humidity.state)
        assert_item_value("Unittest_Output", "OFF")
        item_state_event("Unittest_Humidity", 10)
        self.assertEqual("off", self.humidity.state)
        assert_item_value("Unittest_Output", "OFF")

        # some humidity changes above threshold
        item_state_event("Unittest_Humidity", 65)
        self.assertEqual("on_HighHumidity", self.humidity.state)
        assert_item_value("Unittest_Output", "ON")
        item_state_event("Unittest_Humidity", 100)
        self.assertEqual("on_HighHumidity", self.humidity.state)
        assert_item_value("Unittest_Output", "ON")

        # humidity below threshold again
        item_state_event("Unittest_Humidity", 50)
        self.assertEqual("on_Extended", self.humidity.state)
        assert_item_value("Unittest_Output", "ON")

        # humidity above threshold again
        item_state_event("Unittest_Humidity", 70)
        self.assertEqual("on_HighHumidity", self.humidity.state)
        assert_item_value("Unittest_Output", "ON")

        # humidity below threshold again and timeout
        item_state_event("Unittest_Humidity", 64)
        self.assertEqual("on_Extended", self.humidity.state)
        assert_item_value("Unittest_Output", "ON")
        call_timeout(self.transitions_timer_mock)
        self.assertEqual("off", self.humidity.state)
        assert_item_value("Unittest_Output", "OFF")
