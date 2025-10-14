"""Tests for motion sensors."""

import collections
import pathlib
import sys
import unittest
import unittest.mock

import HABApp

import habapp_rules.sensors.config.humidity
import habapp_rules.sensors.humidity
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer


class TestMotion(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing motion sensors rule."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Humidity", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_Output", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_Unittest_Output_state", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Custom_Name", None)

        config = habapp_rules.sensors.config.humidity.HumiditySwitchConfig(items=habapp_rules.sensors.config.humidity.HumiditySwitchItems(humidity="Unittest_Humidity", output="Unittest_Output", state="H_Unittest_Output_state"))

        self.humidity = habapp_rules.sensors.humidity.HumiditySwitch(config)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "Humidity"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        humidity_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self.humidity.states, transitions=self.humidity.trans, initial=self.humidity.state, show_conditions=True)

        humidity_graph.get_graph().draw(picture_dir / "Humidity.png", format="png", prog="dot")

    def test_init(self) -> None:
        """Test init."""
        full_config = habapp_rules.sensors.config.humidity.HumiditySwitchConfig(
            items=habapp_rules.sensors.config.humidity.HumiditySwitchItems(humidity="Unittest_Humidity", output="Unittest_Output", state="Custom_Name"),
            parameter=habapp_rules.sensors.config.humidity.HumiditySwitchParameter(absolute_threshold=70, extended_time=42),
        )

        humidity = habapp_rules.sensors.humidity.HumiditySwitch(full_config)
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
                tests.helper.oh_item.set_state("Unittest_Humidity", test_case.humidity_value)
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
                tests.helper.oh_item.set_state("Unittest_Humidity", test_case.item_value)
                self.assertEqual(test_case.expected_result, self.humidity._check_high_humidity(test_case.given_value))

    def test_cb_humidity(self) -> None:
        """Test _cb_humidity."""
        with (
            unittest.mock.patch.object(self.humidity, "high_humidity_start") as start_mock,
            unittest.mock.patch.object(self.humidity, "high_humidity_end") as end_mock,
            unittest.mock.patch.object(self.humidity, "_check_high_humidity", return_value=True) as check_mock,
        ):
            tests.helper.oh_item.item_state_event("Unittest_Humidity", 99)
            check_mock.assert_called_once_with(99)
            start_mock.assert_called_once()
            end_mock.assert_not_called()

        with (
            unittest.mock.patch.object(self.humidity, "high_humidity_start") as start_mock,
            unittest.mock.patch.object(self.humidity, "high_humidity_end") as end_mock,
            unittest.mock.patch.object(self.humidity, "_check_high_humidity", return_value=False) as check_mock,
        ):
            tests.helper.oh_item.item_state_event("Unittest_Humidity", 42)
            check_mock.assert_called_once_with(42)
            start_mock.assert_not_called()
            end_mock.assert_called_once()

    def test_states(self) -> None:
        """Test states."""
        self.assertEqual("off", self.humidity.state)

        # some humidity changes below threshold
        tests.helper.oh_item.item_state_event("Unittest_Humidity", 64)
        self.assertEqual("off", self.humidity.state)
        tests.helper.oh_item.assert_value("Unittest_Output", "OFF")
        tests.helper.oh_item.item_state_event("Unittest_Humidity", 10)
        self.assertEqual("off", self.humidity.state)
        tests.helper.oh_item.assert_value("Unittest_Output", "OFF")

        # some humidity changes above threshold
        tests.helper.oh_item.item_state_event("Unittest_Humidity", 65)
        self.assertEqual("on_HighHumidity", self.humidity.state)
        tests.helper.oh_item.assert_value("Unittest_Output", "ON")
        tests.helper.oh_item.item_state_event("Unittest_Humidity", 100)
        self.assertEqual("on_HighHumidity", self.humidity.state)
        tests.helper.oh_item.assert_value("Unittest_Output", "ON")

        # humidity below threshold again
        tests.helper.oh_item.item_state_event("Unittest_Humidity", 50)
        self.assertEqual("on_Extended", self.humidity.state)
        tests.helper.oh_item.assert_value("Unittest_Output", "ON")

        # humidity above threshold again
        tests.helper.oh_item.item_state_event("Unittest_Humidity", 70)
        self.assertEqual("on_HighHumidity", self.humidity.state)
        tests.helper.oh_item.assert_value("Unittest_Output", "ON")

        # humidity below threshold again and timeout
        tests.helper.oh_item.item_state_event("Unittest_Humidity", 64)
        self.assertEqual("on_Extended", self.humidity.state)
        tests.helper.oh_item.assert_value("Unittest_Output", "ON")
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        self.assertEqual("off", self.humidity.state)
        tests.helper.oh_item.assert_value("Unittest_Output", "OFF")
