"""Test version."""
import HABApp.openhab.items

import habapp_rules.__version__
import habapp_rules.core.version
import tests.helper.oh_item
import tests.helper.test_case_base


class TestSetVersions(tests.helper.test_case_base.TestCaseBase):
	"""Test for SetVersions."""

	def setUp(self) -> None:
		"""Set up test case."""
		tests.helper.test_case_base.TestCaseBase.setUp(self)

		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_habapp_version", None)
		tests.helper.oh_item.add_mock_item(HABApp.openhab.items.StringItem, "H_habapp_rules_version", None)

		habapp_rules.core.version.SetVersions()

	def test_version_values(self):
		"""test if versions were set correctly."""
		tests.helper.oh_item.assert_value("H_habapp_version", HABApp.__version__)
		tests.helper.oh_item.assert_value("H_habapp_rules_version", habapp_rules.__version__.__version__)
