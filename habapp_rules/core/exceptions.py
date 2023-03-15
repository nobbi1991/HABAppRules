"""Exceptions for HabAppRules."""


class HabAppRulesException(Exception):
	"""Exception which is raised by this package."""


class HabAppRulesConfigurationException(HabAppRulesException):
	"""Exception which is raised if wrong configuration is given"""
