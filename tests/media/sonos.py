import collections
import pathlib
import sys
import unittest

import HABApp
from HABApp.openhab.definitions import ThingStatusEnum

import habapp_rules.media.config.sonos
import habapp_rules.media.sonos
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
from habapp_rules.media.config.sonos import ContentLineIn, ContentPlayUri, ContentTuneIn


class TestSonos(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing Sonos."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_thing("Unittest:SonosMin")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_State_min", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_PowerSwitch_min", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.PlayerItem, "Unittest_Player_min", None)

        tests.helper.oh_item.add_mock_thing("Unittest:SonosMax")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_State_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_PowerSwitch_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.PlayerItem, "Unittest_Player_max", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_PlayUri_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_CurrentTrackUri_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_TuneInStationId_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_LineIn_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_FavoriteId_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_DisplayString_max", None)

        config_min = habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(sonos_thing="Unittest:SonosMin", state="Unittest_State_min", power_switch="Unittest_PowerSwitch_min", sonos_player="Unittest_Player_min"),
            parameter=habapp_rules.media.config.sonos.SonosParameter(),
        )

        self._config_max = habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(
                sonos_thing="Unittest:SonosMin",
                state="Unittest_State_min",
                power_switch="Unittest_PowerSwitch_min",
                sonos_player="Unittest_Player_min",
                play_uri="Unittest_PlayUri_max",
                current_track_uri="Unittest_CurrentTrackUri_max",
                tune_in_station_id="Unittest_TuneInStationId_max",
                line_in="Unittest_LineIn_max",
                favorite_id="Unittest_FavoriteId_max",
                display_string="Unittest_DisplayString_max",
            ),
            parameter=habapp_rules.media.config.sonos.SonosParameter(),
        )

        self.sonos_min = habapp_rules.media.sonos.Sonos(config_min)
        self.sonos_max = habapp_rules.media.sonos.Sonos(self._config_max)

    @unittest.skipIf(sys.platform != "win32", "Should only run on windows when graphviz is installed")
    def test_create_graph(self) -> None:  # pragma: no cover
        """Create state machine graph for documentation."""
        picture_dir = pathlib.Path(__file__).parent / "_state_charts" / "Sonos"
        if not picture_dir.is_dir():
            picture_dir.mkdir(parents=True)

        jal_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self.sonos_min.states, transitions=self.sonos_min.trans, initial=self.sonos_min.state, show_conditions=False)

        jal_graph.get_graph().draw(picture_dir / "Sonos.png", format="png", prog="dot")

        for state_name in [state for state in self._get_state_names(self.sonos_min.states) if "init" not in state.lower()]:
            jal_graph = tests.helper.graph_machines.HierarchicalGraphMachineTimer(model=tests.helper.graph_machines.FakeModel(), states=self.sonos_min.states, transitions=self.sonos_min.trans, initial=state_name, show_conditions=True)
            jal_graph.get_graph(force_new=True, show_roi=True).draw(picture_dir / f"Sonos_{state_name}.png", format="png", prog="dot")

    def test_initial_state(self) -> None:
        """Test initial state."""
        TestCase = collections.namedtuple("TestCase", "power_switch, thing_status, player, expected_state")

        test_cases = [
            TestCase("OFF", ThingStatusEnum.OFFLINE, "PAUSE", "PowerOff"),
            TestCase("OFF", ThingStatusEnum.OFFLINE, "PLAY", "PowerOff"),
            TestCase("OFF", ThingStatusEnum.ONLINE, "PAUSE", "PowerOff"),
            TestCase("OFF", ThingStatusEnum.ONLINE, "PLAY", "PowerOff"),
            TestCase("ON", ThingStatusEnum.OFFLINE, "PAUSE", "Starting"),
            TestCase("ON", ThingStatusEnum.OFFLINE, "PLAY", "Starting"),
            TestCase("ON", ThingStatusEnum.ONLINE, "PAUSE", "Standby"),
            TestCase("ON", ThingStatusEnum.ONLINE, "PLAY", "Playing_Init"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_PowerSwitch_min", test_case.power_switch)
                tests.helper.oh_item.set_state("Unittest_PowerSwitch_max", test_case.power_switch)
                tests.helper.oh_item.set_thing_state("Unittest:SonosMin", test_case.thing_status)
                tests.helper.oh_item.set_thing_state("Unittest:SonosMax", test_case.thing_status)
                tests.helper.oh_item.set_state("Unittest_Player_min", test_case.player)
                tests.helper.oh_item.set_state("Unittest_Player_max", test_case.player)

                self.assertEqual(test_case.expected_state, self.sonos_min._get_initial_state())
                self.assertEqual(test_case.expected_state, self.sonos_max._get_initial_state())

    def test_on_enter_playing_init(self) -> None:
        """Test on_enter_playing_init."""
        TestCase = collections.namedtuple("TestCase", "tune_in_station_id , current_track_uri , line_in , expected_state_min, expected_state_max")
        self.sonos_max._config.parameter.known_content = [ContentPlayUri(uri="some_stream", display_text="some_stream")]

        test_cases = [
            TestCase(None, None, None, "Playing_UnknownContent", "Playing_UnknownContent"),
            TestCase("", "unknown_content", "OFF", "Playing_UnknownContent", "Playing_UnknownContent"),
            TestCase("", "", "OFF", "Playing_UnknownContent", "Playing_UnknownContent"),
            TestCase("", "", "ON", "Playing_UnknownContent", "Playing_LineIn"),
            TestCase("", "some_stream", "OFF", "Playing_UnknownContent", "Playing_PlayUri"),
            TestCase("", "some_stream", "ON", "Playing_UnknownContent", "Playing_PlayUri"),
            TestCase("42", "", "OFF", "Playing_UnknownContent", "Playing_TuneIn"),
            TestCase("42", "", "ON", "Playing_UnknownContent", "Playing_TuneIn"),
            TestCase("42", "some_stream", "OFF", "Playing_UnknownContent", "Playing_TuneIn"),
            TestCase("42", "some_stream", "ON", "Playing_UnknownContent", "Playing_TuneIn"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_TuneInStationId_max", test_case.tune_in_station_id)
                tests.helper.oh_item.set_state("Unittest_CurrentTrackUri_max", test_case.current_track_uri)
                tests.helper.oh_item.set_state("Unittest_LineIn_max", test_case.line_in)

                self.sonos_min.to_Playing_Init()
                self.sonos_max.to_Playing_Init()

                self.assertEqual(self.sonos_min.state, test_case.expected_state_min)
                self.assertEqual(self.sonos_max.state, test_case.expected_state_max)

    def test_check_if_known_content(self) -> None:
        """Test _check_if_known_content."""
        TestCase = collections.namedtuple("TestCase", "known_content, item_tune_id, item_track_uri, item_line_in, value_tune_in_id, value_track_uri, value_line_in, expected_result")
        known_content = [
            ContentTuneIn(display_text="TuneIn1", tune_in_id=1),
            ContentTuneIn(display_text="TuneIn2", tune_in_id=2),
            ContentPlayUri(display_text="PlayUri1", uri="uri1"),
            ContentPlayUri(display_text="PlayUri2", uri="uri2"),
            ContentLineIn(display_text="LineIn"),
        ]

        test_cases = [
            # item is None
            TestCase([], False, False, False, None, None, None, None),
            TestCase([], False, False, True, None, None, None, None),
            TestCase([], False, True, False, None, None, None, None),
            TestCase([], False, True, True, None, None, None, None),
            TestCase([], True, False, False, None, None, None, None),
            TestCase([], True, False, True, None, None, None, None),
            TestCase([], True, True, False, None, None, None, None),
            TestCase([], True, True, True, None, None, None, None),
            # states but no known_content
            TestCase([], True, True, True, None, None, None, None),
            TestCase([], True, True, True, None, None, "OFF", None),
            TestCase([], True, True, True, None, None, "ON", None),
            # states but with known_content
            TestCase(known_content, True, True, True, None, None, None, None),
            TestCase(known_content, True, True, True, "", "", "OFF", None),
            TestCase(known_content, True, True, True, "", "", "ON", known_content[4]),
            TestCase(known_content, True, True, True, "", "uri2", "OFF", known_content[3]),
            TestCase(known_content, True, True, True, "", "uri2", "ON", known_content[3]),
            TestCase(known_content, True, True, True, "2", "", "OFF", known_content[1]),
            TestCase(known_content, True, True, True, "2", "", "ON", known_content[1]),
            TestCase(known_content, True, True, True, "2", "uri2", "OFF", known_content[1]),
            TestCase(known_content, True, True, True, "2", "uri2", "ON", known_content[1]),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._config_max.items.tune_in_station_id = HABApp.openhab.items.OpenhabItem.get_item("Unittest_TuneInStationId_max") if test_case.item_tune_id else None
                self._config_max.items.current_track_uri = HABApp.openhab.items.OpenhabItem.get_item("Unittest_CurrentTrackUri_max") if test_case.item_track_uri else None
                self._config_max.items.line_in = HABApp.openhab.items.OpenhabItem.get_item("Unittest_LineIn_max") if test_case.item_line_in else None
                self._config_max.parameter.known_content = test_case.known_content

                if test_case.item_tune_id is not None:
                    tests.helper.oh_item.set_state("Unittest_TuneInStationId_max", test_case.value_tune_in_id)
                if test_case.item_track_uri is not None:
                    tests.helper.oh_item.set_state("Unittest_CurrentTrackUri_max", test_case.value_track_uri)
                if test_case.item_line_in is not None:
                    tests.helper.oh_item.set_state("Unittest_LineIn_max", test_case.value_line_in)

                self.assertEqual(test_case.expected_result, self.sonos_max._check_if_known_content())
