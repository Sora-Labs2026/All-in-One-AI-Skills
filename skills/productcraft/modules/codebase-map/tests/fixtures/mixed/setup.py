from setuptools import setup

setup(
    name="legacy",
    entry_points={"console_scripts": ["legacy-tool = legacy.main:run"]},
)
