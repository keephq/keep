from setuptools import setup, find_packages

setup(
    name="fluxcd_provider",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "kubernetes>=24.2.0",
    ],
)
