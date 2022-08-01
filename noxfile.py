import os

import nox
import nox.command


@nox.session
def coverage(session):
	"""Run coverage."""
	session.install("-r", "requirements.txt")
	session.install("-r", "requirements_dev.txt")
	with session.chdir("tests"):
		session.run("python", "-m", "coverage", "run", "run_unittest.py")

		try:
			session.run("python", "-m", "coverage", "html", "--skip-covered", "--fail-under=100")
		except nox.command.CommandFailed as exc:
			if os.name == "nt":
				os.startfile("htmlcov\\index.html")
			raise exc


@nox.session
def pylint(session):
	"""Run pylint."""
	session.install("-r", "requirements.txt")
	session.install("-r", "requirements_dev.txt")
	dirs = [f".\\{directory}" for directory in ("rules", "tests")]
	args = [*dirs, "--rcfile=.pylintrc"]
	session.run("python", "-m", "pylint", *args)
