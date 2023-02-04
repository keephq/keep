"""
Provider configuration model.
"""
from dataclasses import dataclass


@dataclass
class ProviderConfig:
    """
    Provider configuration model.

    Args:
        name (str): The name of the provider.
        type (str): The type of the provider.
        config (dict): The configuration for the provider.
    """

    id: str
    description: str
    provider_type: str
    authentication: dict
