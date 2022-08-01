import typing

import setuptools


def load_req() -> typing.List[str]:
	with open('requirements.txt') as f:
		return f.readlines()


setuptools.setup(
	name="habapp_rules",
	version="1.0.0",
	author="Seuling N.",
	description="Basic rules for HABApp",
	packages=setuptools.find_packages(exclude=["tests*", "rules*"]),
	install_requires=load_req(),
	python_requires=">=3.10",
	license="habapp_rules currently has no license model."
)
