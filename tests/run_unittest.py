"""Run all unit-tests."""
import logging
import pathlib
import sys
import unittest.mock

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

EXCLUDED_PY_FILES = ["run_unittest.py", "__init__.py", "rule_runner.py"]
INPUT_MODULES = [f"tests.{'.'.join(f.parts)[:-3]}" for f in pathlib.Path(".").rglob("*.py") if f.name not in EXCLUDED_PY_FILES]

with unittest.mock.patch("logging.getLogger", spec=logging.getLogger):
	result = unittest.TextTestRunner().run(unittest.TestLoader().loadTestsFromNames(INPUT_MODULES))
