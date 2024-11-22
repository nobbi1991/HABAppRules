"""Exceptions for HabAppRules."""


class HabAppRulesError(Exception):
    """Exception which is raised by this package."""


class HabAppRulesConfigurationError(HabAppRulesError):
    """Exception which is raised if wrong configuration is given."""
