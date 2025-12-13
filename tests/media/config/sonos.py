"""Test config models for sonos rules."""

import unittest

import HABApp

import habapp_rules.core.exceptions
import habapp_rules.media.config.sonos
import tests.helper.oh_item
import tests.helper.test_case_base


class TestSonosParameter(unittest.TestCase):
    """Tests for SonosParameter."""

    def setUp(self) -> None:
        """Setup tests."""
        self.known_content_uri_1 = habapp_rules.media.config.sonos.ContentPlayUri(display_text="content 1", favorite_id=1, uri="http://example.com/content1")
        self.known_content_uri_2 = habapp_rules.media.config.sonos.ContentPlayUri(display_text="content 2", favorite_id=2, uri="http://example.com/content2")
        self.known_content_tunein_1 = habapp_rules.media.config.sonos.ContentTuneIn(display_text="content 3", favorite_id=1, tune_in_id=42)

    def test_validate_known_content(self) -> None:
        """Test validate_known_content."""
        # default parameter
        habapp_rules.media.config.sonos.SonosParameter()

        # no overlap
        habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_uri_1, self.known_content_uri_2])

        # overlap
        with self.assertRaises(ValueError):
            habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_uri_1, self.known_content_uri_2, self.known_content_tunein_1])

    def test_check_if_known_tune_in(self) -> None:
        """Test check_if_known_tune_in."""
        # default parameter
        param_config = habapp_rules.media.config.sonos.SonosParameter()
        self.assertIsNone(param_config.check_if_known_tune_in(42))

        # known tune in
        param_config = habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_tunein_1])
        self.assertEqual(param_config.check_if_known_tune_in(42), self.known_content_tunein_1)

        # unknown tune in
        param_config = habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_tunein_1])
        self.assertIsNone(param_config.check_if_known_tune_in(10))

    def test_check_if_known_play_uri(self) -> None:
        """Test check_if_known_play_uri."""
        # default parameter
        param_config = habapp_rules.media.config.sonos.SonosParameter()
        self.assertIsNone(param_config.check_if_known_play_uri("http://example.com/content1"))

        # known play uri
        param_config = habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_uri_1])
        self.assertEqual(param_config.check_if_known_play_uri("http://example.com/content1"), self.known_content_uri_1)

        # unknown play uri
        param_config = habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_uri_1])
        self.assertIsNone(param_config.check_if_known_play_uri("http://example.com/content2"))


class TestSonosConfig(tests.helper.test_case_base.TestCaseBase):
    """Tests for SonosConfig."""

    def setUp(self) -> None:
        """Setup tests."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_thing("Unittest:Sonos")

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_State", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.SwitchItem, "Unittest_PowerSwitch", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.PlayerItem, "Unittest_Player", None)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_PlayUri", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_CurrentTrackUri", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_TuneInStationId", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.DimmerItem, "Unittest_Volume", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_FavoriteId", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_DisplayString", None)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "Unittest_PresenceState", None)

        self.known_content_uri_1 = habapp_rules.media.config.sonos.ContentPlayUri(display_text="content 1", favorite_id=10, uri="http://example.com/content1")
        self.known_content_uri_2 = habapp_rules.media.config.sonos.ContentPlayUri(display_text="content 1", start_volume=10, uri="http://example.com/content1")
        self.known_content_tunein_1 = habapp_rules.media.config.sonos.ContentTuneIn(display_text="content 3", favorite_id=20, tune_in_id=42)

    def test_validate_model(self) -> None:
        """Test validate_model."""
        # default config
        habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", current_track_uri="Unittest_CurrentTrackUri"),
            parameter=habapp_rules.media.config.sonos.SonosParameter(),
        )

        # ContentTuneIn in parameter and tune_in_station_id in items
        habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(
                sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", current_track_uri="Unittest_CurrentTrackUri", tune_in_station_id="Unittest_TuneInStationId"
            ),
            parameter=habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_tunein_1]),
        )

        # ContentTuneIn in parameter and NO tune_in_station_id in items
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.media.config.sonos.SonosConfig(
                items=habapp_rules.media.config.sonos.SonosItems(sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", current_track_uri="Unittest_CurrentTrackUri"),
                parameter=habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_tunein_1]),
            )

        # ContentPlayUri in parameter and play_uri in items
        habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(
                sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", current_track_uri="Unittest_CurrentTrackUri", play_uri="Unittest_PlayUri"
            ),
            parameter=habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_uri_1]),
        )

        # ContentPlayUri in parameter and NO play_uri in items
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.media.config.sonos.SonosConfig(
                items=habapp_rules.media.config.sonos.SonosItems(sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", current_track_uri="Unittest_CurrentTrackUri"),
                parameter=habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_uri_1]),
            )

        # start_volume in parameter and sonos_volume in items
        habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(
                sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", current_track_uri="Unittest_CurrentTrackUri", play_uri="Unittest_PlayUri", sonos_volume="Unittest_Volume"
            ),
            parameter=habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_uri_2]),
        )

        # start_volume in parameter and NO sonos_volume in items
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.media.config.sonos.SonosConfig(
                items=habapp_rules.media.config.sonos.SonosItems(
                    sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", play_uri="Unittest_PlayUri", current_track_uri="Unittest_CurrentTrackUri"
                ),
                parameter=habapp_rules.media.config.sonos.SonosParameter(known_content=[self.known_content_uri_2]),
            )

        # lock_time_volume in parameter and sonos_volume in items
        habapp_rules.media.config.sonos.SonosConfig(
            items=habapp_rules.media.config.sonos.SonosItems(
                sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", current_track_uri="Unittest_CurrentTrackUri", sonos_volume="Unittest_Volume"
            ),
            parameter=habapp_rules.media.config.sonos.SonosParameter(lock_time_volume=10),
        )

        # lock_time_volume in parameter and NO sonos_volume in items
        with self.assertRaises(habapp_rules.core.exceptions.HabAppRulesConfigurationError):
            habapp_rules.media.config.sonos.SonosConfig(
                items=habapp_rules.media.config.sonos.SonosItems(sonos_thing="Unittest:Sonos", state="Unittest_State", power_switch="Unittest_PowerSwitch", sonos_player="Unittest_Player", current_track_uri="Unittest_CurrentTrackUri"),
                parameter=habapp_rules.media.config.sonos.SonosParameter(lock_time_volume=10),
            )
