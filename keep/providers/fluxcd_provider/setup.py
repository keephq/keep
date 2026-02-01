from setuptools import setup, find_packages

setup(
    name="fluxcd_provider",
    version="1.0.0",
    packages=find_packages(),
    install_requires=[
        "kubernetes>=24.2.0,<30.0.0",
        "pydantic>=1.10.0,<2.0.0",
    ],
    author="Keep Team",
    author_email="info@keephq.dev",
    description="Flux CD provider for Keep",
    keywords="keep, fluxcd, gitops, kubernetes",
    url="https://github.com/keephq/keep",
)
