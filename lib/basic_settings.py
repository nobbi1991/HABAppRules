import logging
import os
import pathlib
import sys

habapp_log = logging.getLogger('HABApp.Rules')


def add_rules_path() -> None:
    """Add rules path to sys.path. This is necessary that imports from other files are possible."""
    if os.name == "posix":
        top_lvl_path = str(pathlib.Path.cwd() / "config/config")
    elif os.name == "nt":
        top_lvl_path = str(pathlib.Path.cwd())
    else:
        habapp_log.warning(f"Could not detect OS by name = {os.name}")
        top_lvl_path = None

    if top_lvl_path and top_lvl_path not in sys.path:
        habapp_log.info(f"Add {top_lvl_path} to sys.path")
        sys.path.append(top_lvl_path)


add_rules_path()
