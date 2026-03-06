"""OpenAI AI provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class OpenAIProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "OpenAI API Key", "sensitive": True},
        default=""
    )

class OpenAIProvider(BaseProvider):
    """OpenAI AI provider."""
    
    PROVIDER_DISPLAY_NAME = "OpenAI"
    PROVIDER_CATEGORY = ["AI/ML"]
    OPENAI_API = "https://api.openai.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = OpenAIProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, prompt: str = "", model: str = "gpt-3.5-turbo", **kwargs: Dict[str, Any]):
        if not prompt:
            raise ProviderException("Prompt is required")

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}]
        }

        try:
            response = requests.post(
                f"{self.OPENAI_API}/chat/completions",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"OpenAI API error: {e}")

        self.logger.info("OpenAI completion created")
        return {"status": "success", "response": response.json().get("choices", [{}])[0].get("message", {}).get("content", "")}
