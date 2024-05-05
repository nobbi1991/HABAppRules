"""Setup project."""

import pathlib

import setuptools

import habapp_rules.__version__


def load_req() -> list[str]:
    """Load requirements.

    :return: All requirements as list
    """
    with pathlib.Path("requirements.txt").open(encoding="utf-8") as f:
        return f.readlines()


VERSION = habapp_rules.__version__.__version__

setuptools.setup(
    name="habapp_rules",
    version=VERSION,
    author="Seuling N.",
    description="Basic rules for HABApp",
    long_description="Basic rules for HABApp",
    packages=setuptools.find_packages(exclude=["tests*", "rules*"]),
    install_requires=load_req(),
    python_requires=">=3.10",
    license="Apache License 2.0",
    package_data={"": ["*.html"]},
)
