"""Module to create donut charts."""

import collections.abc
import pathlib

import matplotlib.pyplot as plt

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

    Args:
        labels: labels for the pie chart
        values: values of the pie chart
        chart_path: target path for the chart
    """
    _, ax = plt.subplots()
    pie_result = ax.pie(values, labels=labels, colors=CHART_COLORS, autopct=_auto_percent_format(values), pctdistance=0.7, textprops={"fontsize": 10})
    texts = pie_result[1]
    for text in texts:
        text.set_backgroundcolor("white")

    plt.savefig(str(chart_path), bbox_inches="tight", transparent=True)


def create_history_chart(months: list[str], values: list[float], chart_path: pathlib.Path) -> None:
    """Create a bar chart showing monthly consumption history.

    Args:
        months: ordered month labels, oldest → newest
        values: monthly consumption in kWh, matching months
        chart_path: target path for the chart
    """
    _, ax = plt.subplots(figsize=(6, 2.4))
    bars = ax.bar(months, values, color=CHART_COLORS[0])
    ax.set_ylabel("kWh")
    for bar_label in ax.bar_label(bars, fmt="{:.1f}", padding=3, fontsize=9):
        bar_label.set_bbox({"facecolor": "white", "edgecolor": "none", "pad": 1})
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for label in ax.get_xticklabels() + ax.get_yticklabels():
        label.set_bbox({"facecolor": "white", "edgecolor": "none", "pad": 1})
    plt.xticks(rotation=90, ha="right")
    plt.tight_layout()
    plt.savefig(str(chart_path), bbox_inches="tight", transparent=True)
    plt.close()
