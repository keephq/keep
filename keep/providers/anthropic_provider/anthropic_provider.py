"""Anthropic Claude AI provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AnthropicProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Anthropic API Key", "sensitive": True},
        default=""
    )

class AnthropicProvider(BaseProvider):
    """Anthropic Claude AI provider."""
    
    PROVIDER_DISPLAY_NAME = "Anthropic"
    PROVIDER_CATEGORY = ["AI/ML"]
    ANTHROPIC_API = "https://api.anthropic.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AnthropicProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, prompt: str = "", model: str = "claude-3-opus-20240229", **kwargs: Dict[str, Any]):
        if not prompt:
            raise ProviderException("Prompt is required")

        payload = {
            "model": model,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }

        try:
            response = requests.post(
                f"{self.ANTHROPIC_API}/messages",
                json=payload,
                headers={
                    "x-api-key": self.authentication_config.api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                timeout=60
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Anthropic API error: {e}")

        self.logger.info("Anthropic completion created")
        return {"status": "success", "response": response.json().get("content", [{}])[0].get("text", "")}
