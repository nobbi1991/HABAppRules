"""Nox sessions."""
import pathlib
import subprocess
import sys

try:
    import nose_helper.nox_checks.common
except ImportError as exc:
    with (pathlib.Path.cwd() / "requirements_dev.txt").open() as req_file:
        nose_pkg = next((pkg for pkg in req_file.read().split("\n") if pkg.startswith("nose_helper")), None)
        if not nose_pkg:
            raise Exception("nose_helper package is missing in requirements_dev.txt") from exc  # noqa: TRY002
        subprocess.check_call([sys.executable, "-m", "pip", "install", nose_pkg])  # noqa: S603
    import nose_helper.nox_checks.common

import nox

PYTHON_VERSION = ["3.10", "3.11"]
nox.options.sessions = ["version_check", "coverage", "ruff"]


class Nox(nose_helper.nox_checks.common.NoxBase):
    """Class for all nox sessions."""

    def __init__(self, session: nox.Session) -> None:
        """Init nox."""
        nose_helper.nox_checks.common.NoxBase.__init__(self, session, project_name="habapp_rules", changelog_path=pathlib.Path().resolve() / "changelog.md")


@nox.session(python=PYTHON_VERSION)
def coverage(session: nox.Session) -> None:
    """Run coverage."""
    Nox(session).coverage()


@nox.session(python=PYTHON_VERSION)
def ruff(session: nox.Session) -> None:
    """Run ruff."""
    Nox(session).ruff()


@nox.session(python=PYTHON_VERSION)
def version_check(session: nox.Session) -> None:
    """Check if version was updated."""
    Nox(session).version_check()
