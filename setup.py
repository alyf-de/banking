from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in banking/__init__.py
from banking import __version__ as version

setup(
	name="banking",
	version=version,
	description="Banking Integration by ALYF GmbH",
	author="ALYF GmbH",
	author_email="hallo@alyf.de",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires,
)
