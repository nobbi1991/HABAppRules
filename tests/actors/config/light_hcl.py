"""Test config models for HCL light rules."""

import collections

import habapp_rules.actors.config.light_hcl
import tests.helper.test_case_base


class TestLightHclConfig(tests.helper.test_case_base.TestCaseBase):
    """Test HCL config."""

    def test_sorted_color_config(self) -> None:
        """Test sorting of HCL values."""
        TestCase = collections.namedtuple("TestCase", "input, output")

        test_cases = [TestCase([(-1, 42), (0, 100), (1, 500)], [(-1, 42), (0, 100), (1, 500)]), TestCase([(0, 100), (-1, 42), (1, 500)], [(-1, 42), (0, 100), (1, 500)]), TestCase([(1, 500), (0, 100), (-1, 42)], [(-1, 42), (0, 100), (1, 500)])]

        for test_case in test_cases:
            with self.subTest(test_case=test_case):
                parameter = habapp_rules.actors.config.light_hcl.HclElevationParameter(color_map=test_case.input)
                self.assertEqual(test_case.output, parameter.color_map)
