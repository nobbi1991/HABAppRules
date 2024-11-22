import json
import logging
import pathlib
import sys

import requests

import habapp_rules

POSITIVE_RESPONSE_CODE = 200
VERSION_LENGTH = 3

logging.basicConfig(
    level=logging.INFO,  # Set the logging level (INFO, DEBUG, etc.)
    format="%(levelname)s: %(message)s",  # Log message format
    handlers=[logging.StreamHandler(sys.stdout)],  # Use sys.stdout for logs
)

LOGGER = logging.getLogger(__name__)


class VersionCheck:
    """Checker to asure that version was updated."""

    def __init__(self, current_version: str, pypi_pkg_name: str, changelog_path: str | None = None) -> None:
        """Create checker.

        Args:
            current_version: Version of the current branch. E.g 1.1.0
            pypi_pkg_name: Name of the PyPi package
            changelog_path: path to changelog file
        """
        self.current_version = current_version
        self.pypi_pkg_name = pypi_pkg_name
        self.changelog_path = pathlib.Path(changelog_path) if changelog_path else None

    def __get_pypi_version(self) -> str:
        """Get the newest version from PyPi.

        Returns:
                Returns the newest version which is released on PyPi

        Raises:
        ConnectionError: if no response was received
        """
        result = requests.get(f"https://pypi.org/pypi/{self.pypi_pkg_name}/json", timeout=10)
        if result.status_code != POSITIVE_RESPONSE_CODE:
            msg = "no response!"
            raise ConnectionError(msg)

        return json.loads(result.text)["info"]["version"]

    @staticmethod
    def __str_to_version(version: str) -> int:
        """Get a integer representation for a given version as string.

        Args:
            version: Version as string. E.g. 1.1.0

        Returns:
            A integer representation of the given version

        Raises:
        AttributeError: if the format of the given version is not correct
        """
        version_parts = version.split(".")

        if len(version_parts) != VERSION_LENGTH or not all(value.isdigit() for value in version_parts):
            msg = f"The format of the given version ({version}) is not correct. Version must have the following format X.X.X"
            raise AttributeError(msg)

        return int(version_parts[0]) * 1000000 + int(version_parts[1]) * 1000 + int(version_parts[2])

    def check_version(self) -> int:
        """Check if version of the current branch is higher than the newest PyPi version.

        Returns:
            0 if branch version is higher than PyPi version. If not -1
        """
        passed = True

        pypi_version = self.__get_pypi_version()
        branch_version = self.current_version

        LOGGER.info(f"PyPi version: {pypi_version} | branch version: {branch_version}")

        if not self.__str_to_version(branch_version) > self.__str_to_version(pypi_version):
            passed = False
            LOGGER.error("Increase version of branch!")

        if self.changelog_path:
            with self.changelog_path.open("r") as changelog_file:
                first_line = changelog_file.readline()

            if branch_version not in first_line:
                LOGGER.error(f"Current version '{branch_version}' must be mentioned in the first line of changelog.md!")
                passed = False

        return 0 if passed else -1


if __name__ == "__main__":
    sys.exit(VersionCheck(habapp_rules.__version__, "habapp_rules", "changelog.md").check_version())
