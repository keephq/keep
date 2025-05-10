"""
Setup file for the Flux CD provider.
"""

from setuptools import setup, find_packages

setup(
    name="keep-fluxcd-provider",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "kubernetes>=28.1.0",
        "pyyaml>=6.0.1",
    ],
)
