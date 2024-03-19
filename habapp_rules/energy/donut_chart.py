"""Module to create donut charts."""
import collections.abc
import pathlib

import matplotlib.pyplot


def __auto_percent_format(values: list[float]) -> collections.abc.Callable:
	"""Get labels for representing the absolute value.

	:param values: list of all values
	:return: function which returns the formatted string if called
	"""

	def my_format(pct: float) -> str:
		"""get formatted value.

		:param pct: percent value
		:return: formatted value
		"""
		total = sum(values)
		return f"{(pct * total / 100.0):.1f} kWh"

	return my_format


def create_chart(labels: list[str], values: list[float], chart_path: pathlib.Path) -> None:
	"""Create the donut chart.

	:param labels: labels for the donut chart
	:param values: values of the donut chart
	:param chart_path: target path for the chart
	"""
	_, ax = matplotlib.pyplot.subplots()
	_, texts, _ = ax.pie(values, labels=labels, autopct=__auto_percent_format(values), pctdistance=0.7, textprops={"fontsize": 10})
	for text in texts:
		text.set_backgroundcolor("white")

	matplotlib.pyplot.savefig(str(chart_path), bbox_inches="tight", transparent=True)
