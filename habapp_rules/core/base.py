"""Base class for all habapp_rules rules."""

import logging

import HABApp

from habapp_rules.core.logger import InstanceLogger


class RuleBase(HABApp.Rule):
    """Base class for all habapp_rules rules.

    Provides a descriptive rule name and an instance logger bound to the module of the concrete rule.
    Subclasses should call ``_log_init_done`` at the end of their ``__init__`` to emit a consistent "init successful" message.
    """

    def __init__(self, name_suffix: str) -> None:
        """Init base rule.

        Args:
            name_suffix: identifier appended to the class name to build the rule name (typically the primary OpenHAB item name)
        """
        HABApp.Rule.__init__(self)
        self.rule_name = f"{type(self).__name__}_{name_suffix}"
        self._instance_logger = InstanceLogger(logging.getLogger(type(self).__module__), name_suffix)

    def _log_init_done(self, additional_info: str = "") -> None:
        """Log a standardized message that the rule was initialized successfully.

        Args:
            additional_info: optional extra information appended to the message
        """
        msg = f"Init of rule '{type(self).__name__}' with name '{self.rule_name}' was successful."
        if additional_info:
            msg = f"{msg} {additional_info}"
        self._instance_logger.debug(msg)
