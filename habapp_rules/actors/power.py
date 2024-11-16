"""Deprecated"""
import warnings  # pragma: no cover

from habapp_rules.sensors.current_switch import CurrentSwitch  # noqa: F401 pylint: disable=unused-import # pragma: no cover

warnings.warn(
	"CurrentSwitch has been moved to 'habapp_rules.sensors.current_switch.py'. Importing it from 'habapp_rules.actors.power.py' is deprecated and will be removed in a future release.",
	DeprecationWarning,
	stacklevel=2
)  # pragma: no cover
