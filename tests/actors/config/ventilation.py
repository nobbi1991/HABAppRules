"""Test ventilation config."""

import datetime
import unittest

import habapp_rules.actors.config.ventilation


class TestStateConfigLongAbsence(unittest.TestCase):
    """Test ventilation config."""

    def test_default_config(self) -> None:
        """Test default config."""
        default_config = habapp_rules.actors.config.ventilation.StateConfigLongAbsence(42, "some text", 12)

        self.assertEqual(42, default_config.level)
        self.assertEqual("some text", default_config.display_text)
        self.assertEqual(12, default_config.duration)
        self.assertEqual(datetime.time(6), default_config.start_time)
