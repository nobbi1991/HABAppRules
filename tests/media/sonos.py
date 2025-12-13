import collections
import pathlib
import sys
import unittest
import unittest.mock

import HABApp
from HABApp.openhab.definitions import ThingStatusEnum

import habapp_rules.media.config.sonos
import habapp_rules.media.sonos
import habapp_rules.system
import tests.helper.graph_machines
import tests.helper.oh_item
import tests.helper.test_case_base
import tests.helper.timer
from habapp_rules.media.config.sonos import ContentPlayUri, ContentTuneIn, SonosParameter


class TestSonos(tests.helper.test_case_base.TestCaseBaseStateMachine):
    """Tests cases for testing Sonos."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBaseStateMachine.setUp(self)

        tests.helper.oh_item.add_mock_thing("Unittest:SonosMin")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_State_min", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.PlayerItem, "Unittest_Player_min", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_CurrentTrackUri_min", None)

        tests.helper.oh_item.add_mock_thing("Unittest:SonosMax")
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_State_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_PowerSwitch_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.PlayerItem, "Unittest_Player_max", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_PlayUri_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_CurrentTrackUri_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_TuneInStationId_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Volume_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_FavoriteId_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_DisplayString_max", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_PresenceState", None)

        self._config_min = habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(sonos_thing="Unittest:SonosMin", state="Unittest_State_min", sonos_player="Unittest_Player_min", current_track_uri="Unittest_CurrentTrackUri_min"),
            parameter=habapp_rules.media.config.sonos.SonosParameter(),
        )

        self._config_max = habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(
                sonos_thing="Unittest:SonosMax",
                state="Unittest_State_max",
                power_switch="Unittest_PowerSwitch_max",
                sonos_player="Unittest_Player_max",
                play_uri="Unittest_PlayUri_max",
                current_track_uri="Unittest_CurrentTrackUri_max",
                tune_in_station_id="Unittest_TuneInStationId_max",
                sonos_volume="Unittest_Volume_max",
                favorite_id="Unittest_FavoriteId_max",
                display_string="Unittest_DisplayString_max",
                presence_state="Unittest_PresenceState",
            ),
            parameter=habapp_rules.media.config.sonos.SonosParameter(),
        )

        self.sonos_min = habapp_rules.media.sonos.Sonos(self._config_min)
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
        TestCase = collections.namedtuple("TestCase", "power_switch, thing_status, player, expected_state_min, expected_state_max")

        test_cases = [
            TestCase("OFF", ThingStatusEnum.OFFLINE, "PAUSE", "PowerOff", "PowerOff"),
            TestCase("OFF", ThingStatusEnum.OFFLINE, "PLAY", "PowerOff", "PowerOff"),
            TestCase("OFF", ThingStatusEnum.ONLINE, "PAUSE", "Standby", "Standby"),
            TestCase("OFF", ThingStatusEnum.ONLINE, "PLAY", "Playing_Init", "Playing_Init"),
            TestCase("ON", ThingStatusEnum.OFFLINE, "PAUSE", "PowerOff", "Booting"),
            TestCase("ON", ThingStatusEnum.OFFLINE, "PLAY", "PowerOff", "Booting"),
            TestCase("ON", ThingStatusEnum.ONLINE, "PAUSE", "Standby", "Standby"),
            TestCase("ON", ThingStatusEnum.ONLINE, "PLAY", "Playing_Init", "Playing_Init"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                tests.helper.oh_item.set_state("Unittest_PowerSwitch_max", test_case.power_switch)
                tests.helper.oh_item.set_thing_state("Unittest:SonosMin", test_case.thing_status)
                tests.helper.oh_item.set_thing_state("Unittest:SonosMax", test_case.thing_status)
                tests.helper.oh_item.set_state("Unittest_Player_min", test_case.player)
                tests.helper.oh_item.set_state("Unittest_Player_max", test_case.player)

                self.assertEqual(test_case.expected_state_min, self.sonos_min._get_initial_state())
                self.assertEqual(test_case.expected_state_max, self.sonos_max._get_initial_state())

    def test_on_enter_playing_init(self) -> None:
        """Test on_enter_playing_init."""
        TestCase = collections.namedtuple("TestCase", "current_track_uri, expected_state")

        test_cases = [
            TestCase(None, "Playing_UnknownContent"),
            TestCase("", "Playing_UnknownContent"),
            TestCase("x-file-cifs:some_stream", "Playing_PlayUri"),
            TestCase("tunein:some_stream", "Playing_TuneIn"),
            TestCase("some_tunein_stream", "Playing_TuneIn"),
            TestCase("x-sonos-htastream:some_stream", "Playing_LineIn"),
            TestCase("some_stream", "Playing_UnknownContent"),
            TestCase("spotify", "Playing_UnknownContent"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._config_max.items.current_track_uri.value = test_case.current_track_uri
                self.sonos_max.to_Playing_Init()
                self.assertEqual(test_case.expected_state, self.sonos_max.state)

    def test_on_enter_starting(self) -> None:
        """Test on_enter_Starting."""
        # state is pause
        self._config_min.items.sonos_player.value = "PAUSE"
        self._config_max.items.sonos_player.value = "PAUSE"

        self.sonos_min.to_Starting()
        self.sonos_max.to_Starting()

        self.assertEqual(self.sonos_min.state, "Starting")
        self.assertEqual(self.sonos_max.state, "Starting")

        # state is play
        self._config_min.items.sonos_player.value = "PLAY"
        self._config_max.items.sonos_player.value = "PLAY"

        self.sonos_min.to_Starting()
        self.sonos_max.to_Starting()

        self.assertEqual(self.sonos_min.state, "Playing_UnknownContent")
        self.assertEqual(self.sonos_max.state, "Playing_UnknownContent")

    def test_set_outputs(self) -> None:
        """Test set_outputs."""
        self.sonos_max.state = "Playing_UnknownContent"
        with (
            unittest.mock.patch.object(self.sonos_max, "_check_if_known_content") as mock_check_if_known_content,
            unittest.mock.patch.object(self.sonos_max, "_set_start_volume") as mock_set_start_volume,
            unittest.mock.patch.object(self.sonos_max, "_set_outputs_display_text") as mock_set_outputs_display_text,
            unittest.mock.patch.object(self.sonos_max, "_set_outputs_favorite_id") as mock_set_outputs_favorite_id,
        ):
            self.sonos_max._set_outputs()
            mock_check_if_known_content.assert_called_once()
            mock_set_start_volume.assert_called_once_with(mock_check_if_known_content.return_value)
            mock_set_outputs_display_text.assert_called_once_with(mock_check_if_known_content.return_value)
            mock_set_outputs_favorite_id.assert_called_once_with(mock_check_if_known_content.return_value)

    def test_set_outputs_display_text(self) -> None:
        """Test set_outputs_display_text."""
        TestCase = collections.namedtuple("TestCase", "state, known_content, expected_text")

        content_tune_in = ContentTuneIn(display_text="TuneIn1", tune_in_id=1)
        content_play_uri = ContentPlayUri(display_text="PlayUri1", uri="uri1")

        test_cases = [
            # no known content
            TestCase("PowerOff", None, "Off"),
            TestCase("Booting", None, "Booting"),
            TestCase("Standby", None, "Standby"),
            TestCase("Starting", None, "Starting"),
            TestCase("Playing_Init", None, "Playing"),
            TestCase("Playing_UnknownContent", None, "Playing"),
            TestCase("Playing_TuneIn", None, "Playing"),
            TestCase("Playing_PlayUri", None, "Playing"),
            TestCase("Playing_LineIn", None, "TV"),
            # known content for states where it does not matter
            TestCase("PowerOff", content_tune_in, "Off"),
            TestCase("Booting", content_tune_in, "Booting"),
            TestCase("Standby", content_tune_in, "Standby"),
            TestCase("Starting", content_tune_in, "[TuneIn1]"),
            TestCase("Playing_LineIn", content_tune_in, "TV"),
            # known content where it matters
            TestCase("Playing_TuneIn", content_tune_in, "TuneIn1"),
            TestCase("Playing_PlayUri", content_play_uri, "PlayUri1"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.sonos_min.state = test_case.state
                self.sonos_max.state = test_case.state

                self.sonos_min._set_outputs_display_text(test_case.known_content)
                self.sonos_max._set_outputs_display_text(test_case.known_content)

                tests.helper.oh_item.assert_value("Unittest_DisplayString_max", test_case.expected_text)

    def test_set_outputs_favorite_id(self) -> None:
        """Test set_outputs_favorite_id."""
        tests.helper.oh_item.assert_value("Unittest_FavoriteId_max", 0)
        tests.helper.oh_item.assert_value("Unittest_State_max", "PowerOff")

        # playing unknown content
        self.sonos_max.to_Playing_Init()
        self.sonos_max._set_outputs_favorite_id(None)
        tests.helper.oh_item.assert_value("Unittest_FavoriteId_max", -1)

        # playing unknown content (with favorite_id_unknown_content set)
        self.sonos_max._config.parameter.favorite_id_unknown_content = 255
        self.sonos_max.to_Playing_Init()
        self.sonos_max._set_outputs_favorite_id(None)
        tests.helper.oh_item.assert_value("Unittest_FavoriteId_max", 255)

        # playing with known content
        self.sonos_max.to_Playing_Init()
        self.sonos_max._set_outputs_favorite_id(ContentTuneIn(tune_in_id=1, favorite_id=42, display_text="TuneIn1"))
        tests.helper.oh_item.assert_value("Unittest_FavoriteId_max", 42)

        # previous state is not set
        self.sonos_max._previous_state = None
        self.sonos_max.to_Starting()

        # Standby from Playing
        self.sonos_max._previous_state = "Playing_UnknownContent"
        self.sonos_max.to_Standby()
        tests.helper.oh_item.assert_value("Unittest_FavoriteId_max", 0)

        # Standby from Booting and _started_through_favorite_id
        self.sonos_max._previous_state = "Booting"
        self.sonos_max._started_through_favorite_id = True
        with unittest.mock.patch.object(self.sonos_max, "_get_favorite_content_by_id") as mock_get_fav_content_by_id, unittest.mock.patch.object(self.sonos_max, "_set_favorite_content") as mock_set_favorite_content:
            self.sonos_max.to_Standby()
            mock_set_favorite_content.assert_called_once_with(mock_get_fav_content_by_id.return_value)

    def test_check_if_known_content(self) -> None:
        """Test _check_if_known_content."""
        TestCase = collections.namedtuple("TestCase", "state, known_content, current_track_uri,  station_id, expected_result")

        known_content = [
            ContentTuneIn(display_text="TuneIn1", tune_in_id=1),
            ContentTuneIn(display_text="TuneIn2", tune_in_id=2),
            ContentPlayUri(display_text="PlayUri1", uri="uri1"),
            ContentPlayUri(display_text="PlayUri2", uri="uri2"),
        ]

        test_cases = [
            # Standby
            TestCase("Standby", [], "", "", None),
            TestCase("Standby", [], "", "2", None),
            TestCase("Standby", [], "uri2", "", None),
            TestCase("Standby", [], "uri2", "2", None),
            TestCase("Standby", known_content, "", "", None),
            TestCase("Standby", known_content, "", "2", None),
            TestCase("Standby", known_content, "uri2", "", None),
            TestCase("Standby", known_content, "uri2", "2", None),
            # PlayUri
            TestCase("Playing_PlayUri", [], "", "", None),
            TestCase("Playing_PlayUri", [], "", "2", None),
            TestCase("Playing_PlayUri", [], "uri2", "", None),
            TestCase("Playing_PlayUri", [], "uri2", "2", None),
            TestCase("Playing_PlayUri", known_content, "", "", None),
            TestCase("Playing_PlayUri", known_content, "", "2", None),
            TestCase("Playing_PlayUri", known_content, "uri2", "", known_content[3]),
            TestCase("Playing_PlayUri", known_content, "uri2", "2", known_content[3]),
            # TuneIn
            TestCase("Playing_TuneIn", [], "", "", None),
            TestCase("Playing_TuneIn", [], "", "2", None),
            TestCase("Playing_TuneIn", [], "uri2", "", None),
            TestCase("Playing_TuneIn", [], "uri2", "2", None),
            TestCase("Playing_TuneIn", known_content, "", "", None),
            TestCase("Playing_TuneIn", known_content, "", "2", known_content[1]),
            TestCase("Playing_TuneIn", known_content, "uri2", "", None),
            TestCase("Playing_TuneIn", known_content, "uri2", "2", known_content[1]),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.sonos_max.state = test_case.state
                self._config_max.parameter.known_content = test_case.known_content
                self._config_max.items.current_track_uri.value = test_case.current_track_uri

                if not test_case.station_id:
                    self._config_max.items.tune_in_station_id = None
                else:
                    self._config_max.items.tune_in_station_id = HABApp.openhab.items.OpenhabItem.get_item("Unittest_TuneInStationId_max")
                    self._config_max.items.tune_in_station_id.value = test_case.station_id

                self.assertEqual(test_case.expected_result, self.sonos_max._check_if_known_content())

    def test_set_start_volume(self) -> None:
        """Test _set_start_volume."""
        # just to be sure that sonos min does not raise
        self.sonos_min._set_start_volume(None)
        self.sonos_min._set_start_volume(ContentTuneIn(display_text="TuneIn1", tune_in_id=1))

        parameter_none = SonosParameter(
            known_content=[],
            start_volume_tune_in=None,
            start_volume_line_in=None,
            start_volume_unknown=None,
        )

        paremter_volumes_set = SonosParameter(
            known_content=[],
            start_volume_tune_in=10,
            start_volume_line_in=20,
            start_volume_unknown=30,
        )

        content_tune_in = ContentTuneIn(display_text="TuneIn1", tune_in_id=1, start_volume=90)
        content_play_uri = ContentPlayUri(display_text="PlayUri1", uri="uri1", start_volume=95)

        TestCase = collections.namedtuple("TestCase", "config_parameter, locked, state, known_content, expected_volume")

        test_cases = [
            # parameter not set | not locked
            TestCase(config_parameter=parameter_none, locked=False, state="Standby", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=False, state="Standby", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=False, state="Standby", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=False, state="Starting", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=False, state="Starting", known_content=content_tune_in, expected_volume=90),
            TestCase(config_parameter=parameter_none, locked=False, state="Starting", known_content=content_play_uri, expected_volume=95),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_TuneIn", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_TuneIn", known_content=content_tune_in, expected_volume=90),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_TuneIn", known_content=content_play_uri, expected_volume=95),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_LineIn", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_LineIn", known_content=content_tune_in, expected_volume=90),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_LineIn", known_content=content_play_uri, expected_volume=95),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_UnknownContent", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_UnknownContent", known_content=content_tune_in, expected_volume=90),
            TestCase(config_parameter=parameter_none, locked=False, state="Playing_UnknownContent", known_content=content_play_uri, expected_volume=95),
            # parameter not set | locked
            TestCase(config_parameter=parameter_none, locked=True, state="Standby", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Standby", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Standby", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Starting", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Starting", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Standby", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_TuneIn", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_TuneIn", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_TuneIn", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_LineIn", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_LineIn", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_LineIn", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_UnknownContent", known_content=None, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_UnknownContent", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=parameter_none, locked=True, state="Playing_UnknownContent", known_content=content_play_uri, expected_volume=None),
            # parameter set | not locked
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Standby", known_content=None, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Standby", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Standby", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Starting", known_content=None, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Starting", known_content=content_tune_in, expected_volume=90),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Starting", known_content=content_play_uri, expected_volume=95),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_TuneIn", known_content=None, expected_volume=10),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_TuneIn", known_content=content_tune_in, expected_volume=90),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_TuneIn", known_content=content_play_uri, expected_volume=95),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_LineIn", known_content=None, expected_volume=20),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_LineIn", known_content=content_tune_in, expected_volume=90),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_LineIn", known_content=content_play_uri, expected_volume=95),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_UnknownContent", known_content=None, expected_volume=30),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_UnknownContent", known_content=content_tune_in, expected_volume=90),
            TestCase(config_parameter=paremter_volumes_set, locked=False, state="Playing_UnknownContent", known_content=content_play_uri, expected_volume=95),
            # parameter set | locked
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Standby", known_content=None, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Standby", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Standby", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Starting", known_content=None, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Starting", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Standby", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_TuneIn", known_content=None, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_TuneIn", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_TuneIn", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_LineIn", known_content=None, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_LineIn", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_LineIn", known_content=content_play_uri, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_UnknownContent", known_content=None, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_UnknownContent", known_content=content_tune_in, expected_volume=None),
            TestCase(config_parameter=paremter_volumes_set, locked=True, state="Playing_UnknownContent", known_content=content_play_uri, expected_volume=None),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self._config_max.parameter = test_case.config_parameter
                self.sonos_max._volume_locked = test_case.locked
                self.sonos_max.state = test_case.state

                with unittest.mock.patch.object(self.sonos_max._volume_observer, "send_command") as mock_send_volume:
                    self.sonos_max._set_start_volume(test_case.known_content)

                    if test_case.expected_volume:
                        mock_send_volume.assert_called_once_with(test_case.expected_volume)
                    else:
                        mock_send_volume.assert_not_called()

    def test_get_favorite_content_by_id(self) -> None:
        """Test _get_favorite_content_by_id."""
        TestCase = collections.namedtuple("TestCase", "fav_id_arg, fav_id_item, known_content, expected_content")

        known_content = [ContentTuneIn(display_text="TuneIn1", tune_in_id=1, favorite_id=42), ContentPlayUri(display_text="PlayUri1", uri="uri1", favorite_id=44)]

        test_cases = [
            # fav id from item
            TestCase(None, None, [], None),
            TestCase(None, None, known_content, None),
            TestCase(None, None, [], None),
            TestCase(None, None, known_content, None),
            TestCase(None, 17, [], None),
            TestCase(None, 17, known_content, None),
            TestCase(None, 17, [], None),
            TestCase(None, 17, known_content, None),
            TestCase(None, 42, [], None),
            TestCase(None, 42, known_content, known_content[0]),
            TestCase(None, 42, [], None),
            TestCase(None, 42, known_content, known_content[0]),
            TestCase(None, 44, [], None),
            TestCase(None, 44, known_content, known_content[1]),
            TestCase(None, 44, [], None),
            TestCase(None, 44, known_content, known_content[1]),
            # fav id from arg | item is None
            TestCase(17, None, [], None),
            TestCase(17, None, known_content, None),
            TestCase(17, None, [], None),
            TestCase(17, None, known_content, None),
            TestCase(42, None, [], None),
            TestCase(42, None, known_content, known_content[0]),
            TestCase(42, None, [], None),
            TestCase(42, None, known_content, known_content[0]),
            TestCase(44, None, [], None),
            TestCase(44, None, known_content, known_content[1]),
            TestCase(44, None, [], None),
            TestCase(44, None, known_content, known_content[1]),
            # fav id from arg | item is not None, but will be ignored
            TestCase(17, 42, [], None),
            TestCase(17, 42, known_content, None),
            TestCase(17, 42, [], None),
            TestCase(17, 42, known_content, None),
            TestCase(42, 44, [], None),
            TestCase(42, 44, known_content, known_content[0]),
            TestCase(42, 44, [], None),
            TestCase(42, 44, known_content, known_content[0]),
            TestCase(44, 42, [], None),
            TestCase(44, 42, known_content, known_content[1]),
            TestCase(44, 42, [], None),
            TestCase(44, 42, known_content, known_content[1]),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.sonos_max._config.items.favorite_id.value = test_case.fav_id_item
                self.sonos_max._config.parameter.known_content = test_case.known_content

                if test_case.fav_id_arg is not None:
                    self.assertEqual(test_case.expected_content, self.sonos_max._get_favorite_content_by_id(test_case.fav_id_arg))
                    self.assertIsNone(self.sonos_min._get_favorite_content_by_id(test_case.fav_id_arg))
                else:
                    self.assertEqual(test_case.expected_content, self.sonos_max._get_favorite_content_by_id())
                    self.assertIsNone(self.sonos_min._get_favorite_content_by_id())

    def test_set_favorite_content(self) -> None:
        """Test _set_favorite_content."""
        # TuneIn
        with unittest.mock.patch.object(self._config_max.items.tune_in_station_id, "oh_send_command") as send_tune_in_mock, unittest.mock.patch.object(self._config_max.items.play_uri, "oh_send_command") as send_play_uri_mock:
            self.sonos_max._set_favorite_content(ContentTuneIn(display_text="TuneIn1", tune_in_id=123))
        send_tune_in_mock.assert_called_once_with("123")
        send_play_uri_mock.assert_not_called()

        # PlayUri
        with unittest.mock.patch.object(self._config_max.items.tune_in_station_id, "oh_send_command") as send_tune_in_mock, unittest.mock.patch.object(self._config_max.items.play_uri, "oh_send_command") as send_play_uri_mock:
            self.sonos_max._set_favorite_content(ContentPlayUri(display_text="PlayUri1", uri="uri1"))
        send_tune_in_mock.assert_not_called()
        send_play_uri_mock.assert_called_once_with("uri1")

        # None
        with unittest.mock.patch.object(self._config_max.items.tune_in_station_id, "oh_send_command") as send_tune_in_mock, unittest.mock.patch.object(self._config_max.items.play_uri, "oh_send_command") as send_play_uri_mock:
            self.sonos_max._set_favorite_content(None)
        send_tune_in_mock.assert_not_called()
        send_play_uri_mock.assert_not_called()

    def test_cb_volume(self) -> None:
        """Test _cb_volume."""
        # no lock time
        self.sonos_max._config.parameter.lock_time_volume = None
        self.assertFalse(self.sonos_max._volume_locked)
        tests.helper.oh_item.item_state_change_event("Unittest_Volume_max", 42)
        self.assertFalse(self.sonos_max._volume_locked)

        # with lock time
        self._config_max.parameter.lock_time_volume = 10
        self.sonos_max = habapp_rules.media.sonos.Sonos(self._config_max)
        self.assertFalse(self.sonos_max._volume_locked)
        tests.helper.oh_item.item_state_change_event("Unittest_Volume_max", 45)
        self.assertTrue(self.sonos_max._volume_locked)

    def test_cb_countdown_volume_lock(self) -> None:
        """Test _cb_countdown_volume_lock."""
        self.sonos_max._volume_locked = True
        self.sonos_max._cb_countdown_volume_lock()
        self.assertFalse(self.sonos_max._volume_locked)

    def test_cb_favorite_id(self) -> None:
        """Test _cb_favorite_id."""
        # unknown content
        self.sonos_max.to_Standby()
        tests.helper.oh_item.item_state_change_event("Unittest_FavoriteId_max", -1)
        tests.helper.oh_item.assert_value("Unittest_State_max", "Standby")

        # favorite id == 0 (stop) | playing state
        tests.helper.oh_item.set_state("Unittest_Player_max", "PLAY")
        self.sonos_max.to_Playing_Init()
        tests.helper.oh_item.assert_value("Unittest_State_max", "Playing_UnknownContent")
        tests.helper.oh_item.item_state_change_event("Unittest_FavoriteId_max", 0)
        tests.helper.oh_item.assert_value("Unittest_State_max", "Standby")
        tests.helper.oh_item.assert_value("Unittest_Player_max", "PAUSE")

        # unknown content
        self.sonos_max.to_Standby()
        with unittest.mock.patch.object(self.sonos_max, "_instance_logger") as locker_mock:
            tests.helper.oh_item.item_state_change_event("Unittest_FavoriteId_max", 99)
        tests.helper.oh_item.assert_value("Unittest_State_max", "Standby")
        locker_mock.warning.assert_called_once()

        # known content from plying state
        self.sonos_max.to_Playing_Init()
        tests.helper.oh_item.set_state("Unittest_Player_max", "PLAY")
        fav_content = ContentTuneIn(display_text="TuneIn1", tune_in_id=123)
        with (
            unittest.mock.patch.object(self.sonos_max, "_get_favorite_content_by_id", return_value=fav_content) as get_fav_content_mock,
            unittest.mock.patch.object(self.sonos_max, "_set_favorite_content") as set_fav_content_mock,
        ):
            tests.helper.oh_item.item_state_change_event("Unittest_FavoriteId_max", 17)
        get_fav_content_mock.assert_called_once_with(17)
        set_fav_content_mock.assert_called_once_with(fav_content)
        tests.helper.oh_item.assert_value("Unittest_Player_max", "PAUSE")

        # known content from standby state
        self.sonos_max.to_Standby()
        with (
            unittest.mock.patch.object(self.sonos_max, "_get_favorite_content_by_id", return_value=fav_content) as get_fav_content_mock,
            unittest.mock.patch.object(self.sonos_max, "_set_favorite_content") as set_fav_content_mock,
        ):
            tests.helper.oh_item.item_state_change_event("Unittest_FavoriteId_max", 16)
        get_fav_content_mock.assert_called_once_with(16)
        set_fav_content_mock.assert_called_once_with(fav_content)

        # known content from power off state
        self.sonos_max.to_PowerOff()
        fav_content = ContentTuneIn(display_text="TuneIn1", tune_in_id=123)
        tests.helper.oh_item.set_state("Unittest_PowerSwitch_max", "OFF")
        self.assertFalse(self.sonos_max._started_through_favorite_id)
        with unittest.mock.patch.object(self.sonos_max, "_get_favorite_content_by_id", return_value=fav_content) as get_fav_content_mock:
            tests.helper.oh_item.item_state_change_event("Unittest_FavoriteId_max", 17)
        get_fav_content_mock.assert_called_once_with(17)
        self.assertTrue(self.sonos_max._started_through_favorite_id)
        tests.helper.oh_item.assert_value("Unittest_PowerSwitch_max", "ON")

    def test_cb_current_track_uri(self) -> None:
        """Test _cb_current_track_uri."""
        TestCase = collections.namedtuple("TestCase", ["state", "uri", "expected_state"])
        test_cases = [
            TestCase("Standby", "http://example.com/track", "Starting"),
            TestCase("Standby", "", "Standby"),
            TestCase("Standby", "http://example.com/tunein", "Standby"),
            TestCase("Playing_UnknownContent", "http://example.com/track", "Playing_UnknownContent"),
            TestCase("Playing_UnknownContent", "", "Playing_UnknownContent"),
            TestCase("Playing_TuneIn", "http://example.com/track", "Starting"),
            TestCase("Playing_TuneIn", "", "Playing_TuneIn"),
            TestCase("Playing_PlayUri", "http://example.com/track", "Starting"),
            TestCase("Playing_PlayUri", "", "Playing_PlayUri"),
        ]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                self.sonos_max._set_state(test_case.state)
                tests.helper.oh_item.item_state_change_event("Unittest_CurrentTrackUri_max", test_case.uri)
                tests.helper.oh_item.assert_value("Unittest_State_max", test_case.expected_state)

    def test_cb_presence_state(self) -> None:
        """Test _cb_presence_state."""
        # test if playing is stopped
        self.sonos_max.to_Playing_Init()
        tests.helper.oh_item.item_state_change_event("Unittest_PresenceState", habapp_rules.system.PresenceState.LEAVING.value)
        tests.helper.oh_item.assert_value("Unittest_State_max", "Standby")

        # test that nothing happens if presence state is "presence"
        self.sonos_max.to_Playing_Init()
        tests.helper.oh_item.item_state_change_event("Unittest_PresenceState", habapp_rules.system.PresenceState.PRESENCE.value)
        tests.helper.oh_item.assert_value("Unittest_State_max", "Playing_UnknownContent")

    def test_transitions_power_off(self) -> None:
        """Test transitions of PowerOff state."""
        # power on during power off
        self.sonos_max.to_PowerOff()
        tests.helper.oh_item.item_state_change_event("Unittest_PowerSwitch_max", "ON")
        tests.helper.oh_item.assert_value("Unittest_State_max", "Booting")

        # Sonos Thing online
        self.sonos_max.to_PowerOff()
        tests.helper.oh_item.thing_status_info_changed_event("Unittest:SonosMax", ThingStatusEnum.ONLINE)
        tests.helper.oh_item.assert_value("Unittest_State_max", "Standby")

    def test_transitions_booting(self) -> None:
        """Test transitions of Booting state."""
        # power off during booting
        self.sonos_max.to_Booting()
        tests.helper.oh_item.item_state_change_event("Unittest_PowerSwitch_max", "OFF")
        tests.helper.oh_item.assert_value("Unittest_State_max", "PowerOff")

        # timeout during booting
        self.sonos_max.to_Booting()
        tests.helper.timer.call_timeout(self.transitions_timer_mock)
        tests.helper.oh_item.assert_value("Unittest_State_max", "PowerOff")

        # thing online during booting
        self.sonos_max.to_Booting()
        tests.helper.oh_item.thing_status_info_changed_event("Unittest:SonosMax", ThingStatusEnum.ONLINE)
        tests.helper.oh_item.assert_value("Unittest_State_max", "Standby")

    def test_transitions_standby(self) -> None:
        """Test transitions of Standby state."""
        # power off
        self.sonos_max.to_Standby()
        tests.helper.oh_item.item_state_change_event("Unittest_PowerSwitch_max", "OFF")
        tests.helper.oh_item.assert_value("Unittest_State_max", "PowerOff")

        # player start
        self.sonos_max.to_Standby()
        tests.helper.oh_item.item_state_change_event("Unittest_Player_max", "PLAY")
        tests.helper.oh_item.assert_value("Unittest_State_max", "Playing_UnknownContent")

        # content changed through track uri
        self.sonos_max.to_Standby()
        tests.helper.oh_item.item_state_change_event("Unittest_Player_max", "PAUSE")
        tests.helper.oh_item.item_state_change_event("Unittest_CurrentTrackUri_max", "uri1")
        tests.helper.oh_item.assert_value("Unittest_State_max", "Starting")

        # content change should not be triggered if tunein in current track uri
        self.sonos_max.to_Standby()
        tests.helper.oh_item.item_state_change_event("Unittest_Player_max", "PAUSE")
        tests.helper.oh_item.item_state_change_event("Unittest_CurrentTrackUri_max", "something_tunein")
        tests.helper.oh_item.assert_value("Unittest_State_max", "Standby")

        # content changed by favorite id
        self.sonos_max.to_Standby()
        self.sonos_max._config.parameter.known_content = [ContentTuneIn(tune_in_id=1, favorite_id=42, display_text="TuneIn1")]
        tests.helper.oh_item.item_state_change_event("Unittest_Player_max", "PAUSE")
        tests.helper.oh_item.item_state_change_event("Unittest_FavoriteId_max", 42)
        tests.helper.oh_item.assert_value("Unittest_State_max", "Starting")

    def test_transitions_starting(self) -> None:
        """Test transitions of Starting state."""
        # player start
        self.sonos_max.to_Starting()
        tests.helper.oh_item.item_state_change_event("Unittest_Player_max", "PLAY")
        tests.helper.oh_item.assert_value("Unittest_State_max", "Playing_UnknownContent")

        # player already started before enter of Starting state
        self.sonos_max.to_Starting()
        tests.helper.oh_item.assert_value("Unittest_State_max", "Playing_UnknownContent")

    def test_transitions_playing(self) -> None:
        """Test transitions of Playing state."""
        # player stopped
        self.sonos_max.to_Playing_Init()
        tests.helper.oh_item.item_state_change_event("Unittest_Player_max", "PAUSE")
        tests.helper.oh_item.assert_value("Unittest_State_max", "Standby")

        # power off
        self.sonos_max.to_Playing_Init()
        tests.helper.oh_item.item_state_change_event("Unittest_PowerSwitch_max", "OFF")
        tests.helper.oh_item.assert_value("Unittest_State_max", "PowerOff")
