import pathlib

import nose_helper.nox_checks.common
import nox

PYTHON_VERSION = "3.10"
nox.options.sessions = ["coverage", "pylint"]


class Nox(nose_helper.nox_checks.common.NoxBase):

	def __init__(self, session: nox.Session):
		nose_helper.nox_checks.common.NoxBase.__init__(self, session, project_name="habapp_rules", changelog_path=pathlib.Path().resolve() / "changelog.md")


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
	nox_helper = nose_helper.nox_checks.common.NoxBase(session)
	nose_helper.nox_checks.common.run_combined_sessions(session, [
		("coverage", nox_helper.coverage),
		("pylint", nox_helper.pylint)
	])


@nox.session(python=PYTHON_VERSION)
def combined_release(session: nox.sessions.Session):
	"""Run all tests for release."""
	pkg_nox = nose_helper.nox_checks.common.NoxBase(session)
	nose_helper.nox_checks.common.run_combined_sessions(session, [
		("coverage", pkg_nox.coverage),
		("pylint", pkg_nox.pylint),
		("version_check", pkg_nox.version_check)
	])
