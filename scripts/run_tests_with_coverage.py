import subprocess  # ruff: ignore[suspicious-subprocess-import]
import sys


def run(cmd: str) -> None:
    """Run a command and exit if it fails.

    Args:
        cmd: Command to run
    """
    result = subprocess.run(cmd, check=False, shell=True)  # ruff: ignore[subprocess-popen-with-shell-equals-true]
    if result.returncode != 0:
        sys.exit(result.returncode)


run("uv run coverage run tests/run_unittest.py")
run("uv run coverage html --skip-covered --fail-under=100")
