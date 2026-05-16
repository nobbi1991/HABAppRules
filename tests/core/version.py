"""Test version."""

import platform

import HABApp
from HABApp.openhab.items import StringItem

import habapp_rules
from habapp_rules.core.version import SetVersions
from tests.helper.oh_item import add_mock_item, assert_item_value
from tests.helper.test_case_base import TestCaseBase


class TestSetVersions(TestCaseBase):
    """Test for SetVersions."""

    def setUp(self) -> None:
        """Set up test case."""
        TestCaseBase.setUp(self)

        add_mock_item(StringItem, "H_habapp_version", None)
        add_mock_item(StringItem, "H_habapp_rules_version", None)
        add_mock_item(StringItem, "H_python_version", None)

        SetVersions()

    def test_version_values(self) -> None:
        """Test if versions were set correctly."""
        assert_item_value("H_habapp_version", HABApp.__version__)
        assert_item_value("H_habapp_rules_version", habapp_rules.__version__)
        assert_item_value("H_python_version", platform.python_version())
