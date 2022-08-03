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
		session.run("coverage", "run", "run_unittest.py")

		try:
			if os.name == "nt":
				session.run("python", "-m", "coverage", "html", "--skip-covered", "--fail-under=100", "--omit=*oh_item.py,*rule_runner.py")
			else:
				session.run("python", "-m", "coverage", "report", "--skip-covered", "--fail-under=100", "--omit=*oh_item.py,*rule_runner.py")
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
	session.run("pylint", *args)
