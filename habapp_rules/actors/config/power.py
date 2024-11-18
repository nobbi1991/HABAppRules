"""Deprecated"""

import warnings  # pragma: no cover

from habapp_rules.sensors.config.current_switch import CurrentSwitchConfig, CurrentSwitchItems, CurrentSwitchParameter  # noqa: F401 pylint: disable=unused-import # pragma: no cover

warnings.warn(
    "CurrentSwitch config has been moved to 'habapp_rules.sensors.config.current_switch.py'. Importing it from 'habapp_rules.actors.config.power.py' is deprecated and will be removed in a future release.", DeprecationWarning, stacklevel=2
)  # pragma: no cover
