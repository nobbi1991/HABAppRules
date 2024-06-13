import pathlib
import subprocess
import sys

try:
	import nose_helper.nox_checks.common
except ImportError:
	with (pathlib.Path.cwd() / "requirements_dev.txt").open() as req_file:
		nose_pkg = next((pkg for pkg in req_file.read().split("\n") if pkg.startswith("nose_helper")), None)
		if not nose_pkg:
			raise Exception("nose_helper package is missing in requirements_dev.txt")
		subprocess.check_call([sys.executable, "-m", "pip", "install", nose_pkg])
	import nose_helper.nox_checks.common

import nox

PYTHON_VERSION = ["3.11"]
nox.options.sessions = ["version_check", "coverage", "pylint"]


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
