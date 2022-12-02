from setuptools import setup, find_packages

with open("requirements.txt") as f:
	install_requires = f.read().strip().split("\n")

# get version from __version__ variable in klarna_kosma_integration/__init__.py
from klarna_kosma_integration import __version__ as version

setup(
	name="klarna_kosma_integration",
	version=version,
	description="Klarna Kosma Open Banking Integration",
	author="ALYF GmbH",
	author_email="hallo@alyf.de",
	packages=find_packages(),
	zip_safe=False,
	include_package_data=True,
	install_requires=install_requires
)
