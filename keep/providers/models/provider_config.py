"""
Provider configuration model.
"""

import os
from typing import Optional

import chevron
from pydantic.dataclasses import dataclass


@dataclass
class ProviderScope:
    """
    Provider scope model.

    Args:
        name (str): The name of the scope.
        description (Optional[str]): The description of the scope.
        mandatory (bool): Whether the scope is mandatory.
        mandatory_for_webhook (bool): Whether the scope is mandatory for webhook auto installation.
        documentation_url (Optional[str]): The documentation url of the scope.
        alias (Optional[str]): Another alias of the scope.
    """

    name: str
    description: Optional[str] = None
    mandatory: bool = False
    mandatory_for_webhook: bool = False
    documentation_url: Optional[str] = None
    alias: Optional[str] = None


@dataclass
class ProviderConfig:
    """
    Provider configuration model.

    Args:
        description (Optional[str]): The description of the provider.
        authentication (dict): The configuration for the provider.
    """

    authentication: Optional[dict]
    name: Optional[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        if not self.authentication:
            return
        for key, value in self.authentication.items():
            if (
                isinstance(value, str)
                and value.startswith("{{")
                and value.endswith("}}")
            ):
                self.authentication[key] = chevron.render(value, {"env": os.environ})
