"""Contentful headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ContentfulProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Contentful Access Token", "sensitive": True},
        default=""
    )
    space_id: str = dataclasses.field(
        metadata={"required": True, "description": "Contentful Space ID"},
        default=""
    )
    environment: str = dataclasses.field(
        metadata={"required": True, "description": "Contentful Environment"},
        default="master"
    )

class ContentfulProvider(BaseProvider):
    """Contentful headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Contentful"
    PROVIDER_CATEGORY = ["Content Management"]
    CONTENTFUL_API = "https://api.contentful.com/spaces"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ContentfulProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, content_type: str = "", fields: dict = None, **kwargs: Dict[str, Any]):
        if not content_type or not fields:
            raise ProviderException("Content type and fields are required")

        payload = {
            "fields": fields
        }

        try:
            response = requests.post(
                f"{self.CONTENTFUL_API}/{self.authentication_config.space_id}/environments/{self.authentication_config.environment}/entries",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/vnd.contentful.management.v1+json",
                    "X-Contentful-Content-Type": content_type
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Contentful API error: {e}")

        self.logger.info(f"Contentful entry created: {content_type}")
        return {"status": "success", "content_type": content_type}
