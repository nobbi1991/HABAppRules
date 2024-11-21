"""Test config models for filter rules."""

import HABApp

import habapp_rules.common.config.filter
import tests.helper.oh_item
import tests.helper.test_case_base


class TestExponentialFilterConfig(tests.helper.test_case_base.TestCaseBase):
    """Test ExponentialFilterConfig."""

    def setUp(self) -> None:
        """Setup test case."""
        tests.helper.test_case_base.TestCaseBase.setUp(self)

        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Raw", 0)
        tests.helper.oh_item.add_mock_item(HABApp.openhab.items.NumberItem, "Unittest_Filtered", 0)

    def test_init(self) -> None:
        """Test __init__."""
        # instant_increase and instant_decrease is not set
        habapp_rules.common.config.filter.ExponentialFilterConfig(
            items=habapp_rules.common.config.filter.ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"),
            parameter=habapp_rules.common.config.filter.ExponentialFilterParameter(
                tau=42,
            ),
        )

        # instant_increase is set and instant_decrease is not set
        habapp_rules.common.config.filter.ExponentialFilterConfig(
            items=habapp_rules.common.config.filter.ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"), parameter=habapp_rules.common.config.filter.ExponentialFilterParameter(tau=42, instant_increase=True)
        )

        # instant_increase is not set and instant_decrease is set
        habapp_rules.common.config.filter.ExponentialFilterConfig(
            items=habapp_rules.common.config.filter.ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"), parameter=habapp_rules.common.config.filter.ExponentialFilterParameter(tau=42, instant_decrease=True)
        )

        # instant_increase and instant_decrease is set
        with self.assertRaises(ValueError):
            habapp_rules.common.config.filter.ExponentialFilterConfig(
                items=habapp_rules.common.config.filter.ExponentialFilterItems(raw="Unittest_Raw", filtered="Unittest_Filtered"),
                parameter=habapp_rules.common.config.filter.ExponentialFilterParameter(tau=42, instant_increase=True, instant_decrease=True),
            )
