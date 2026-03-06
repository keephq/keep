"""Squadcast incident provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SquadcastProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Squadcast API Key", "sensitive": True},
        default=""
    )

class SquadcastProvider(BaseProvider):
    """Squadcast incident provider."""
    
    PROVIDER_DISPLAY_NAME = "Squadcast"
    PROVIDER_CATEGORY = ["Incident Management"]
    SQUADCAST_API = "https://api.squadcast.com/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SquadcastProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {"message": message}

        try:
            response = requests.post(
                f"{self.SQUADCAST_API}/incidents",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Squadcast API error: {e}")

        self.logger.info("Squadcast incident created")
        return {"status": "success"}
