"""Set version rules."""
import logging

import HABApp

import habapp_rules.__version__
import habapp_rules.core.helper

LOGGER = logging.getLogger(__name__)


class SetVersions(HABApp.Rule):
	"""Update HABApp and habapp_rules version to OpenHAB items."""

	def __init__(self) -> None:
		"""init rule."""
		HABApp.Rule.__init__(self)
		LOGGER.info("Update versions of OpenHAB items")

		item_version_habapp = habapp_rules.core.helper.create_additional_item("H_habapp_version", "String", "HABApp version")
		item_version_habapp_rules = habapp_rules.core.helper.create_additional_item("H_habapp_rules_version", "String", "habapp_rules version")

		item_version_habapp.oh_send_command(HABApp.__version__)
		item_version_habapp_rules.oh_send_command(habapp_rules.__version__.__version__)
