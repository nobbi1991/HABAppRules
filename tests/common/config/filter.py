"""Test config models for filter rules."""

from HABApp.openhab.items import NumberItem

from habapp_rules.common.config.filter import ExponentialFilterConfig, ExponentialFilterItems, ExponentialFilterParameter
from habapp_rules.core.exceptions import HabAppRulesConfigurationError
from tests.helper.oh_item import add_mock_item
from tests.helper.test_case_base import TestCaseBase


class TestExponentialFilterConfig(TestCaseBase):
    """Test ExponentialFilterConfig."""

    def setUp(self) -> None:
        """Setup test case."""
        TestCaseBase.setUp(self)

        add_mock_item(NumberItem, "Unittest_Raw", 0)
        add_mock_item(NumberItem, "Unittest_Filtered", 0)

    def test_init(self) -> None:
        """Test __init__."""
        # instant_increase and instant_decrease is not set
        ExponentialFilterConfig(
            items=ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"),
            parameter=ExponentialFilterParameter(
                tau=42,
            ),
        )

        # instant_increase is set and instant_decrease is not set
        ExponentialFilterConfig(items=ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"), parameter=ExponentialFilterParameter(tau=42, instant_increase=True))

        # instant_increase is not set and instant_decrease is set
        ExponentialFilterConfig(items=ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"), parameter=ExponentialFilterParameter(tau=42, instant_decrease=True))

        # instant_increase and instant_decrease is set
        with self.assertRaises(HabAppRulesConfigurationError):
            ExponentialFilterConfig(
                items=ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"),
                parameter=ExponentialFilterParameter(tau=42, instant_increase=True, instant_decrease=True),
            )
