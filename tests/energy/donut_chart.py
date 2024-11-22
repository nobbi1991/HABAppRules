"""Tests for donut chart."""

import unittest
import unittest.mock

import habapp_rules.energy.donut_chart


class TestDonutFunctions(unittest.TestCase):
    """Test all donut plot functions."""

    def test_auto_percent_format(self) -> None:
        """Test _auto_percent_format."""
        values = [100, 20, 80]
        percent_values = [val / sum(values) * 100 for val in values]

        label_function = habapp_rules.energy.donut_chart._auto_percent_format(values)

        for idx, percent_value in enumerate(percent_values):
            self.assertEqual(f"{values[idx]:.1f} kWh", label_function(percent_value))

    def test_create_chart(self) -> None:
        """Test create_chart."""
        labels = ["one", "two", "three"]
        values = [1, 2, 3.0]
        path = unittest.mock.MagicMock()

        with unittest.mock.patch("habapp_rules.energy.donut_chart.plt") as pyplot_mock:
            ax_mock = unittest.mock.MagicMock()
            pyplot_mock.subplots.return_value = None, ax_mock
            text_mock_1 = unittest.mock.MagicMock()
            text_mock_2 = unittest.mock.MagicMock()
            ax_mock.pie.return_value = None, [text_mock_1, text_mock_2], None

            habapp_rules.energy.donut_chart.create_chart(labels, values, path)

        pyplot_mock.subplots.assert_called_once()
        ax_mock.pie.assert_called_once_with(values, labels=labels, autopct=unittest.mock.ANY, pctdistance=0.7, textprops={"fontsize": 10})

        text_mock_1.set_backgroundcolor.assert_called_once_with("white")
        text_mock_2.set_backgroundcolor.assert_called_once_with("white")

        pyplot_mock.savefig.assert_called_once_with(str(path), bbox_inches="tight", transparent=True)
