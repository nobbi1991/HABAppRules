import typing

import setuptools

import habapp_rules.__version__


def load_req() -> typing.List[str]:
	with open('requirements.txt') as f:
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
	license="Apache License 2.0"
)
