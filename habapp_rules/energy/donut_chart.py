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
    _, texts, _ = ax.pie(values, labels=labels, autopct=_auto_percent_format(values), pctdistance=0.7, textprops={"fontsize": 10})
    for text in texts:
        text.set_backgroundcolor("white")

    plt.savefig(str(chart_path), bbox_inches="tight", transparent=True)
