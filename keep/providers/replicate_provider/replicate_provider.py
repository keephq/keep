"""Replicate AI provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ReplicateProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Replicate API Token", "sensitive": True},
        default=""
    )

class ReplicateProvider(BaseProvider):
    """Replicate AI provider."""
    
    PROVIDER_DISPLAY_NAME = "Replicate"
    PROVIDER_CATEGORY = ["AI/ML"]
    REPLICATE_API = "https://api.replicate.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ReplicateProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, version: str = "", input_data: Dict = None, **kwargs: Dict[str, Any]):
        if not version or not input_data:
            raise ProviderException("Version and input_data are required")

        payload = {
            "version": version,
            "input": input_data
        }

        try:
            response = requests.post(
                f"{self.REPLICATE_API}/predictions",
                json=payload,
                headers={
                    "Authorization": f"Token {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Replicate API error: {e}")

        self.logger.info("Replicate prediction created")
        return {"status": "success", "id": response.json().get("id")}
