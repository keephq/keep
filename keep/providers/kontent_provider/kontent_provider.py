"""Kontent.ai headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class KontentProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Kontent.ai API Key", "sensitive": True},
        default=""
    )
    project_id: str = dataclasses.field(
        metadata={"required": True, "description": "Kontent.ai Project ID"},
        default=""
    )

class KontentProvider(BaseProvider):
    """Kontent.ai headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Kontent.ai"
    PROVIDER_CATEGORY = ["Content Management"]
    KONTENT_API = "https://manage.kontent.ai/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = KontentProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, item_id: str = "", language: str = "", elements: dict = None, **kwargs: Dict[str, Any]):
        if not item_id:
            raise ProviderException("Item ID is required")

        payload = {
            "language": language or "en-US",
            "elements": elements or {}
        }

        try:
            response = requests.put(
                f"{self.KONTENT_API}/projects/{self.authentication_config.project_id}/items/{item_id}/variants/{language or 'en-US'}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Kontent.ai API error: {e}")

        self.logger.info(f"Kontent.ai content updated: {item_id}")
        return {"status": "success", "item_id": item_id}
