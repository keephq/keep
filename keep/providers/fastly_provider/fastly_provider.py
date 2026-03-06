"""Fastly edge computing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FastlyProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Fastly API Token", "sensitive": True},
        default=""
    )
    service_id: str = dataclasses.field(
        metadata={"required": True, "description": "Fastly Service ID"},
        default=""
    )

class FastlyProvider(BaseProvider):
    """Fastly edge computing provider."""
    
    PROVIDER_DISPLAY_NAME = "Fastly"
    PROVIDER_CATEGORY = ["Network Infrastructure"]
    FASTLY_API = "https://api.fastly.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FastlyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, version: str = "", name: str = "", value: str = "", **kwargs: Dict[str, Any]):
        if not name or not value:
            raise ProviderException("Name and value are required")

        payload = {
            "name": name,
            "value": value
        }

        try:
            response = requests.post(
                f"{self.FASTLY_API}/service/{self.authentication_config.service_id}/version/{version}/snippet",
                json=payload,
                headers={
                    "Fastly-Key": self.authentication_config.api_token,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Fastly API error: {e}")

        self.logger.info(f"Fastly snippet created: {name}")
        return {"status": "success", "name": name}
