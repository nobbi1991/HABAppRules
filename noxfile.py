import os

import nox
import nox.command


@nox.session
def coverage(session):
	"""Run coverage."""
	session.install("-r", "requirements.txt")
	with session.chdir("tests"):
		session.run("python", "-m", "coverage", "run", "run_unittest.py")

		try:
			session.run("python", "-m", "coverage", "html", "--skip-covered", "--fail-under=100")
		except nox.command.CommandFailed:
			os.startfile("htmlcov\\index.html")


@nox.session
def pylint(session):
	"""Run pylint."""
	dirs = [f".\\{directory}" for directory in ("rules", "tests")]
	args = [*dirs, "--rcfile=.pylintrc"]
	session.run("python", "-m", "pylint", *args)
