"""Hugging Face AI provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class HuggingFaceProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Hugging Face API Key", "sensitive": True},
        default=""
    )

class HuggingFaceProvider(BaseProvider):
    """Hugging Face AI provider."""
    
    PROVIDER_DISPLAY_NAME = "Hugging Face"
    PROVIDER_CATEGORY = ["AI/ML"]
    HF_API = "https://api-inference.huggingface.co/models"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HuggingFaceProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, model: str = "", inputs: str = "", **kwargs: Dict[str, Any]):
        if not model or not inputs:
            raise ProviderException("Model and inputs are required")

        try:
            response = requests.post(
                f"{self.HF_API}/{model}",
                json={"inputs": inputs},
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Hugging Face API error: {e}")

        self.logger.info("Hugging Face inference completed")
        return {"status": "success", "response": response.json()}
