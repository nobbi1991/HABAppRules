"""Tests for donut chart."""

import unittest
import unittest.mock

from habapp_rules.energy.charts import CHART_COLORS, _auto_percent_format, create_history_chart, create_pie_chart


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

        with unittest.mock.patch("habapp_rules.energy.charts.Figure") as figure_mock, unittest.mock.patch("habapp_rules.energy.charts.FigureCanvasAgg") as canvas_mock:
            fig_mock = figure_mock.return_value
            ax_mock = unittest.mock.MagicMock()
            fig_mock.subplots.return_value = ax_mock
            text_mock_1 = unittest.mock.MagicMock()
            text_mock_2 = unittest.mock.MagicMock()
            ax_mock.pie.return_value = None, [text_mock_1, text_mock_2], None

            create_pie_chart(labels, values, path)

        figure_mock.assert_called_once_with()
        canvas_mock.assert_called_once_with(fig_mock)
        fig_mock.subplots.assert_called_once_with()
        ax_mock.pie.assert_called_once_with(values, labels=labels, colors=CHART_COLORS, autopct=unittest.mock.ANY, pctdistance=0.7, textprops={"fontsize": 10})

        text_mock_1.set_backgroundcolor.assert_called_once_with("white")
        text_mock_2.set_backgroundcolor.assert_called_once_with("white")

        fig_mock.savefig.assert_called_once_with(str(path), bbox_inches="tight", transparent=True)


class TestHistoryChart(unittest.TestCase):
    """Test create_history_chart."""

    def test_create_history_chart(self) -> None:
        """Test create_history_chart."""
        months = ["Jan", "Feb", "Mär"]
        values = [100.0, 150.0, 120.0]
        path = unittest.mock.MagicMock()

        with unittest.mock.patch("habapp_rules.energy.charts.Figure") as figure_mock, unittest.mock.patch("habapp_rules.energy.charts.FigureCanvasAgg") as canvas_mock:
            fig_mock = figure_mock.return_value
            ax_mock = unittest.mock.MagicMock()
            fig_mock.subplots.return_value = ax_mock
            bars_mock = unittest.mock.MagicMock()
            ax_mock.bar.return_value = bars_mock
            bar_label_mock = unittest.mock.MagicMock()
            ax_mock.bar_label.return_value = [bar_label_mock]
            spine_top_mock = unittest.mock.MagicMock()
            spine_right_mock = unittest.mock.MagicMock()
            ax_mock.spines = {"top": spine_top_mock, "right": spine_right_mock}
            tick_x_mock = unittest.mock.MagicMock()
            tick_y_mock = unittest.mock.MagicMock()
            ax_mock.get_xticklabels.return_value = [tick_x_mock]
            ax_mock.get_yticklabels.return_value = [tick_y_mock]

            create_history_chart(months, values, path)

        figure_mock.assert_called_once_with(figsize=(6, 2.4))
        canvas_mock.assert_called_once_with(fig_mock)
        fig_mock.subplots.assert_called_once_with()
        ax_mock.bar.assert_called_once_with(months, values, color=CHART_COLORS[0])
        ax_mock.set_ylabel.assert_called_once_with("kWh")
        ax_mock.bar_label.assert_called_once_with(bars_mock, fmt="{:.1f}", padding=3, fontsize=9)
        bar_label_mock.set_bbox.assert_called_once_with({"facecolor": "white", "edgecolor": "none", "pad": 1})
        spine_top_mock.set_visible.assert_called_once_with(False)
        spine_right_mock.set_visible.assert_called_once_with(False)
        tick_x_mock.set_bbox.assert_called_once_with({"facecolor": "white", "edgecolor": "none", "pad": 1})
        tick_x_mock.set_rotation.assert_called_once_with(90)
        tick_x_mock.set_horizontalalignment.assert_called_once_with("right")
        tick_y_mock.set_bbox.assert_called_once_with({"facecolor": "white", "edgecolor": "none", "pad": 1})
        fig_mock.tight_layout.assert_called_once_with()
        fig_mock.savefig.assert_called_once_with(str(path), bbox_inches="tight", transparent=True)
