"""Better Stack incident provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BetterStackProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Better Stack API Key", "sensitive": True},
        default=""
    )

class BetterStackProvider(BaseProvider):
    """Better Stack incident provider."""
    
    PROVIDER_DISPLAY_NAME = "Better Stack"
    PROVIDER_CATEGORY = ["Incident Management"]
    BETTERSTACK_API = "https://api.betterstack.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BetterStackProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, name: str = "", description: str = "", **kwargs: Dict[str, Any]):
        if not name:
            raise ProviderException("Incident name is required")

        payload = {
            "incident": {
                "name": name,
                "description": description or name
            }
        }

        try:
            response = requests.post(
                f"{self.BETTERSTACK_API}/incidents",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Better Stack API error: {e}")

        self.logger.info("Better Stack incident created")
        return {"status": "success"}
