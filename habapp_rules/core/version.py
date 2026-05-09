"""Set version rules."""

import logging
import platform
from importlib.metadata import version

import HABApp
from HABApp.openhab.items import StringItem

from habapp_rules import __version__
from habapp_rules.core.helper import create_additional_item

LOGGER = logging.getLogger(__name__)


class SetVersions(HABApp.Rule):
    """Update HABApp and habapp_rules version to OpenHAB items."""

    def __init__(self) -> None:
        """Init rule."""
        HABApp.Rule.__init__(self)
        LOGGER.info("Update versions of OpenHAB items")

        item_version_habapp = create_additional_item("H_habapp_version", StringItem, "HABApp version")
        item_version_habapp_rules = create_additional_item("H_habapp_rules_version", StringItem, "habapp_rules version")
        item_version_python = create_additional_item("H_python_version", StringItem, "Python version")

        item_version_habapp.oh_send_command(version("HABApp"))
        item_version_habapp_rules.oh_send_command(__version__)
        item_version_python.oh_send_command(platform.python_version())
