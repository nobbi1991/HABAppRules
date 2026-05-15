"""Tests for donut chart."""

import unittest
import unittest.mock

from habapp_rules.energy.donut_chart import _auto_percent_format, create_chart, create_history_chart


class TestDonutFunctions(unittest.TestCase):
    """Test all donut plot functions."""

    def test_auto_percent_format(self) -> None:
        """Test _auto_percent_format."""
        values = [100, 20, 80]
        percent_values = [val / sum(values) * 100 for val in values]

        label_function = _auto_percent_format(values)

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

            create_chart(labels, values, path)

        pyplot_mock.subplots.assert_called_once()
        ax_mock.pie.assert_called_once_with(values, labels=labels, autopct=unittest.mock.ANY, pctdistance=0.7, textprops={"fontsize": 10})

        text_mock_1.set_backgroundcolor.assert_called_once_with("white")
        text_mock_2.set_backgroundcolor.assert_called_once_with("white")

        pyplot_mock.savefig.assert_called_once_with(str(path), bbox_inches="tight", transparent=True)


class TestHistoryChart(unittest.TestCase):
    """Test create_history_chart."""

    def test_create_history_chart(self) -> None:
        """Test create_history_chart."""
        months = ["Jan", "Feb", "Mär"]
        values = [100.0, 150.0, 120.0]
        path = unittest.mock.MagicMock()

        with unittest.mock.patch("habapp_rules.energy.donut_chart.plt") as pyplot_mock:
            ax_mock = unittest.mock.MagicMock()
            pyplot_mock.subplots.return_value = None, ax_mock
            bars_mock = unittest.mock.MagicMock()
            ax_mock.bar.return_value = bars_mock

            create_history_chart(months, values, path)

        pyplot_mock.subplots.assert_called_once_with(figsize=(10, 4))
        ax_mock.bar.assert_called_once_with(months, values, color="steelblue")
        ax_mock.set_ylabel.assert_called_once_with("kWh")
        ax_mock.bar_label.assert_called_once_with(bars_mock, fmt="{:.1f}", padding=3, fontsize=9)
        pyplot_mock.xticks.assert_called_once_with(rotation=45, ha="right")
        pyplot_mock.tight_layout.assert_called_once()
        pyplot_mock.savefig.assert_called_once_with(str(path), bbox_inches="tight", transparent=True)
        pyplot_mock.close.assert_called_once()
