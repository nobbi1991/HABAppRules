import os

import nox
import nox.command

python_version = "3.10"


@nox.session(python=python_version)
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


@nox.session(python=python_version)
def pylint(session):
	"""Run pylint."""
	session.install("-r", "requirements.txt")
	session.install("-r", "requirements_dev.txt")
	dir_names = ["habapp_rules", "tests"]
	args = [*dir_names, "--rcfile=.pylintrc"]
	session.run("python", "-m", "pylint", *args)
