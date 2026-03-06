"""Cosmic JS headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class CosmicJSProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Cosmic JS API Key", "sensitive": True},
        default=""
    )
    bucket_slug: str = dataclasses.field(
        metadata={"required": True, "description": "Cosmic JS Bucket Slug"},
        default=""
    )

class CosmicJSProvider(BaseProvider):
    """Cosmic JS headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Cosmic JS"
    PROVIDER_CATEGORY = ["Content Management"]
    COSMICJS_API = "https://api.cosmicjs.com/v3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CosmicJSProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, type_slug: str = "", title: str = "", content: str = "", **kwargs: Dict[str, Any]):
        if not type_slug or not title:
            raise ProviderException("Type slug and title are required")

        payload = {
            "title": title,
            "type_slug": type_slug,
            "content": content
        }

        try:
            response = requests.post(
                f"{self.COSMICJS_API}/buckets/{self.authentication_config.bucket_slug}/objects",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Cosmic JS API error: {e}")

        self.logger.info(f"Cosmic JS object created: {title}")
        return {"status": "success", "title": title}
