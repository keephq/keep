"""Cohere AI provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class CohereProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Cohere API Key", "sensitive": True},
        default=""
    )

class CohereProvider(BaseProvider):
    """Cohere AI provider."""
    
    PROVIDER_DISPLAY_NAME = "Cohere"
    PROVIDER_CATEGORY = ["AI/ML"]
    COHERE_API = "https://api.cohere.ai/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CohereProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, prompt: str = "", model: str = "command", **kwargs: Dict[str, Any]):
        if not prompt:
            raise ProviderException("Prompt is required")

        payload = {
            "model": model,
            "prompt": prompt
        }

        try:
            response = requests.post(
                f"{self.COHERE_API}/generate",
                json=payload,
                headers={
                    "Authorization": f"BEARER {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Cohere API error: {e}")

        self.logger.info("Cohere generation completed")
        return {"status": "success", "response": response.json().get("generations", [{}])[0].get("text", "")}
