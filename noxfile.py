import pathlib
import sys

import nox.command

sys.path.append(str(pathlib.Path(__file__).parent.resolve() / "helper"))
from helper.nox_checks.common import NoxBase, run_combined_sessions

PYTHON_VERSION = "3.10"
nox.options.sessions = ["coverage", "pylint"]


class Nox(NoxBase):

	def __init__(self, session: nox.Session):
		NoxBase.__init__(self, session, project_name="habapp_rules")


@nox.session(python=PYTHON_VERSION)
def coverage(session):
	"""Run coverage"""
	Nox(session).coverage()


@nox.session(python=PYTHON_VERSION)
def pylint(session):
	"""Run pylint."""
	Nox(session).pylint()


@nox.session(python=PYTHON_VERSION)
def version_check(session):
	"""Check if version was updated."""
	Nox(session).version_check()


@nox.session(python=PYTHON_VERSION)
def combined_merge(session: nox.sessions.Session):
	"""Run all tests for merge."""
	nox_helper = NoxBase(session)
	run_combined_sessions(session, [
		("coverage", nox_helper.coverage),
		("pylint", nox_helper.pylint)
	])


@nox.session(python=PYTHON_VERSION)
def combined_release(session: nox.sessions.Session):
	"""Run all tests for release."""
	pkg_nox = NoxBase(session)
	run_combined_sessions(session, [
		("coverage", pkg_nox.coverage),
		("pylint", pkg_nox.pylint),
		("version_check", pkg_nox.version_check)
	])
