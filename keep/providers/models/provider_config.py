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
