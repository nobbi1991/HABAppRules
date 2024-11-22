"""Setup logger."""

import collections.abc
import logging
import typing

import HABApp.config.config
import HABApp.config.logging

import habapp_rules

LOG_PATH = HABApp.config.config.CONFIG.directories.logging.absolute()


def setup_logger() -> None:
    """Setup the logger."""
    log_formatter = logging.Formatter("%(asctime)s.%(msecs)03d | %(threadName)20s | %(levelname)8s | %(name)s:%(lineno)d | %(message)s", datefmt="%Y-%m-%d | %H:%M:%S")
    habapp_rules_logger = logging.getLogger("habapp_rules")
    habapp_rules_logger.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    console_handler.setLevel(logging.DEBUG)
    habapp_rules_logger.addHandler(console_handler)

    if not LOG_PATH.is_dir():
        LOG_PATH.mkdir(parents=True)

    file_handler = HABApp.config.logging.MidnightRotatingFileHandler(LOG_PATH / "habapp_rules.log", encoding="utf-8", maxBytes=1_048_576, backupCount=5)
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(logging.DEBUG)
    habapp_rules_logger.addHandler(file_handler)


class InstanceLogger(logging.LoggerAdapter):
    """Logging adapter to add the instance name to the log message."""

    def __init__(self, logger: logging.Logger, instance_name: str) -> None:
        """Instantiate a logging adapter for multiple instances.

        Args:
            logger: the underlying logger e.g. module logger
            instance_name: the name of the instance
        """
        self._instance_name = instance_name
        logging.LoggerAdapter.__init__(self, logger)

    def process(self, msg: str, kwargs: collections.abc.MutableMapping[str, typing.Any]) -> tuple[str, collections.abc.MutableMapping[str, typing.Any]]:
        """Add the instance name to log message.

        Args:
            msg: the log message
            kwargs: additional keyword arguments.

        Returns:
            tuple of msg with given keyword arguments
        """
        return f"{self._instance_name} | {msg}", kwargs


setup_logger()
LOGGER = logging.getLogger(__name__)
LOGGER.info(f"Start logging of habapp_rules. Version = {habapp_rules.__version__}")
