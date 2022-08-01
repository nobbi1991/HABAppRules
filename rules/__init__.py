# pylint: skip-file
import logging
import pathlib
import sys

habapp_log = logging.getLogger('HABApp.Rules')
BASE_PATH = pathlib.Path(__file__).parent.parent.resolve()


def add_rules_path() -> None:
	"""Add rules path to sys.path. This is necessary that imports from other files are possible."""
	if str(BASE_PATH) not in sys.path:
		habapp_log.info(f"Add {BASE_PATH} to sys.path")
		sys.path.append(str(BASE_PATH))


add_rules_path()
# todo: remove this file!