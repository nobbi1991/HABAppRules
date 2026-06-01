"""Module to create donut charts."""

import collections.abc
import pathlib

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

CHART_COLORS = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC"]


def _auto_percent_format(values: list[float]) -> collections.abc.Callable:
    """Get labels for representing the absolute value.

    Args:
        values: list of all values

    Returns:
        function which returns the formatted string if called
    """

    def my_format(pct: float) -> str:
        """Get formatted value.

        Args:
            pct: percent value

        Returns:
            formatted value
        """
        total = sum(values)
        return f"{(pct * total / 100.0):.1f} kWh"

    return my_format


def create_pie_chart(labels: list[str], values: list[float], chart_path: pathlib.Path) -> None:
    """Create the pie chart.

    Uses the object-oriented matplotlib API (isolated ``Figure`` + ``FigureCanvasAgg``) instead of the global ``pyplot`` state, because this function runs in a HABApp worker thread and ``pyplot`` is not thread-safe.

    Args:
        labels: labels for the pie chart
        values: values of the pie chart
        chart_path: target path for the chart
    """
    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    pie_result = ax.pie(values, labels=labels, colors=CHART_COLORS, autopct=_auto_percent_format(values), pctdistance=0.7, textprops={"fontsize": 10})
    texts = pie_result[1]
    for text in texts:
        text.set_backgroundcolor("white")

    fig.savefig(str(chart_path), bbox_inches="tight", transparent=True)


def create_history_chart(months: list[str], values: list[float], chart_path: pathlib.Path) -> None:
    """Create a bar chart showing monthly consumption history.

    Uses the object-oriented matplotlib API (isolated ``Figure`` + ``FigureCanvasAgg``) instead of the global ``pyplot`` state, because this function runs in a HABApp worker thread and ``pyplot`` is not thread-safe.

    Args:
        months: ordered month labels, oldest → newest
        values: monthly consumption in kWh, matching months
        chart_path: target path for the chart
    """
    fig = Figure(figsize=(6, 2.4))
    FigureCanvasAgg(fig)
    ax = fig.subplots()
    bars = ax.bar(months, values, color=CHART_COLORS[0])
    ax.set_ylabel("kWh")
    for bar_label in ax.bar_label(bars, fmt="{:.1f}", padding=3, fontsize=9):
        bar_label.set_bbox({"facecolor": "white", "edgecolor": "none", "pad": 1})
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for label in ax.get_xticklabels():
        label.set_bbox({"facecolor": "white", "edgecolor": "none", "pad": 1})
        label.set_rotation(90)
        label.set_horizontalalignment("right")
    for label in ax.get_yticklabels():
        label.set_bbox({"facecolor": "white", "edgecolor": "none", "pad": 1})
    fig.tight_layout()
    fig.savefig(str(chart_path), bbox_inches="tight", transparent=True)
