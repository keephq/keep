"""Storyblok headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class StoryblokProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Storyblok Access Token", "sensitive": True},
        default=""
    )
    space_id: str = dataclasses.field(
        metadata={"required": True, "description": "Storyblok Space ID"},
        default=""
    )

class StoryblokProvider(BaseProvider):
    """Storyblok headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Storyblok"
    PROVIDER_CATEGORY = ["Content Management"]
    STORYBLOK_API = "https://api.storyblok.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = StoryblokProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, content_type: str = "", name: str = "", slug: str = "", **kwargs: Dict[str, Any]):
        if not content_type or not name:
            raise ProviderException("Content type and name are required")

        payload = {
            "story": {
                "name": name,
                "slug": slug or name.lower().replace(" ", "-"),
                "content": kwargs.get("content", {})
            },
            "publish": kwargs.get("publish", 0)
        }

        try:
            response = requests.post(
                f"{self.STORYBLOK_API}/spaces/{self.authentication_config.space_id}/stories",
                json=payload,
                headers={
                    "Authorization": self.authentication_config.access_token,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Storyblok API error: {e}")

        self.logger.info(f"Storyblok story created: {name}")
        return {"status": "success", "name": name}
