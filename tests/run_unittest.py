"""Run all unit-tests."""

import logging
import pathlib
import sys
import unittest.mock

sys.path.append(str(pathlib.Path(__file__).resolve().parent.parent))

# Get the project root directory (one level up from tests/)
PROJECT_ROOT = pathlib.Path(__file__).parent.parent
TESTS_DIR = PROJECT_ROOT / "tests"

EXCLUDED_PY_FILES = ["run_unittest.py", "__init__.py", "rule_runner.py"]
INPUT_MODULES = [f"{'.'.join(f.relative_to(PROJECT_ROOT).parts)[:-3]}" for f in TESTS_DIR.rglob("*.py") if f.name not in EXCLUDED_PY_FILES]


logger_mock = unittest.mock.MagicMock()
logger_mock.level = logging.WARNING


def run_tests() -> unittest.TestResult:
    """Run the tests and return the result object.

    Returns:
        result object of all tests
    """
    with unittest.mock.patch("logging.getLogger", return_value=logger_mock):
        # Create a test suite from all test modules
        test_suite = unittest.TestLoader().loadTestsFromNames(INPUT_MODULES)

        # Run the tests with verbosity=2 for detailed output
        runner = unittest.TextTestRunner(verbosity=2, failfast=False)
        return runner.run(test_suite)


if __name__ == "__main__":
    result = run_tests()

    # Print a summary of the test results

    # If there were failures or errors, print details
    if result.failures or result.errors:
        for _test, _traceback in result.failures + result.errors:
            pass

    # Exit with non-zero code if there were failures or errors
    sys.exit(not result.wasSuccessful())
