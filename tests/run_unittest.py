"""Run all unit-tests."""

import logging
import pathlib
import sys
import unittest.mock

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

EXCLUDED_PY_FILES = ["run_unittest.py", "__init__.py", "rule_runner.py"]
INPUT_MODULES = [f"{'.'.join(f.parts)[:-3]}" for f in pathlib.Path("tests").rglob("*.py") if f.name not in EXCLUDED_PY_FILES]

logger_mock = unittest.mock.MagicMock()
logger_mock.level = logging.WARNING

with unittest.mock.patch("logging.getLogger", return_value=logger_mock):
    result = unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromNames(INPUT_MODULES))
