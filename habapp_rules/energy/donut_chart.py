"""Module to create donut charts."""

import collections.abc
import pathlib

import matplotlib.pyplot as plt


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


def create_chart(labels: list[str], values: list[float], chart_path: pathlib.Path) -> None:
    """Create the donut chart.

    Args:
        labels: labels for the donut chart
        values: values of the donut chart
        chart_path: target path for the chart
    """
    _, ax = plt.subplots()
    pie_result = ax.pie(values, labels=labels, autopct=_auto_percent_format(values), pctdistance=0.7, textprops={"fontsize": 10})
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
    _, ax = plt.subplots(figsize=(10, 4))
    bars = ax.bar(months, values, color="steelblue")
    ax.set_ylabel("kWh")
    ax.bar_label(bars, fmt="{:.1f}", padding=3, fontsize=9)
    plt.xticks(rotation=45, ha="right")
    plt.tight_layout()
    plt.savefig(str(chart_path), bbox_inches="tight", transparent=True)
    plt.close()
