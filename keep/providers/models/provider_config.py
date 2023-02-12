"""
Provider configuration model.
"""
import os
from dataclasses import dataclass
from typing import Optional

import chevron


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

    authentication: dict
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
