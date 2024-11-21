"""Unit tests for habapp_rules logger."""

import logging
import unittest
import unittest.mock

import habapp_rules.core.logger


class TestLoggerFunctions(unittest.TestCase):
    """Tests for all logger functions."""

    def test_setup_logger(self) -> None:
        """Test setup_logger."""
        stream_handler_mock = unittest.mock.MagicMock()
        file_handler_mock = unittest.mock.MagicMock()

        with unittest.mock.patch("logging.StreamHandler", return_value=stream_handler_mock), unittest.mock.patch("HABApp.config.logging.MidnightRotatingFileHandler", return_value=file_handler_mock):
            habapp_rules.core.logger.setup_logger()

            stream_handler_mock.setFormatter.assert_called_once()
            stream_handler_mock.setLevel.assert_called_once_with(logging.DEBUG)

            file_handler_mock.setFormatter.assert_called_once()
            file_handler_mock.setLevel.assert_called_once_with(logging.DEBUG)

            # path is existing
            with unittest.mock.patch("pathlib.Path.is_dir", return_value=False), unittest.mock.patch("pathlib.Path.mkdir") as makedirs_mock:
                habapp_rules.core.logger.setup_logger()
                makedirs_mock.assert_called_once_with(parents=True)

            # path is not existing
            with unittest.mock.patch("pathlib.Path.is_dir", return_value=True), unittest.mock.patch("pathlib.Path.mkdir") as makedirs_mock:
                habapp_rules.core.logger.setup_logger()
                makedirs_mock.assert_not_called()

        # remove handler
        habapp_rules_logger = logging.getLogger("habapp_rules")
        habapp_rules_logger.removeHandler(stream_handler_mock)
        habapp_rules_logger.removeHandler(file_handler_mock)


class TestInstanceLogger(unittest.TestCase):
    """Test for instanceLogger."""

    def test_instance_logger(self) -> None:
        """Test instance_logger."""
        instance_logger = habapp_rules.core.logger.InstanceLogger(logging.getLogger(__name__), "test_instance")

        self.assertEqual("test_instance", instance_logger._instance_name)
        self.assertEqual(("test_instance | test message", {}), instance_logger.process("test message", {}))
