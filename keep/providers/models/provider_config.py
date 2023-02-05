"""
Provider configuration model.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class ProviderConfig:
    """
    Provider configuration model.

    Args:
        id (str): The name of the provider.
        provider_type (str): The type of the provider.
        description (Optional[str]): The description of the provider.
        authentication (dict): The configuration for the provider.
    """

    id: str
    authentication: dict
    description: Optional[str] = None
