"""Confluence wiki provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ConfluenceProviderAuthConfig:
    url: str = dataclasses.field(
        metadata={"required": True, "description": "Confluence URL"},
        default=""
    )
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Username"},
        default=""
    )
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "API Token", "sensitive": True},
        default=""
    )

class ConfluenceProvider(BaseProvider):
    """Confluence wiki provider."""
    
    PROVIDER_DISPLAY_NAME = "Confluence"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ConfluenceProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, space_key: str = "", title: str = "", content: str = "", **kwargs: Dict[str, Any]):
        if not space_key or not title:
            raise ProviderException("Space key and title are required")

        payload = {
            "type": "page",
            "title": title,
            "space": {"key": space_key},
            "body": {
                "storage": {
                    "value": content or title,
                    "representation": "storage"
                }
            }
        }

        try:
            response = requests.post(
                f"{self.authentication_config.url}/rest/api/content",
                json=payload,
                auth=(self.authentication_config.username, self.authentication_config.api_token),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Confluence API error: {e}")

        self.logger.info("Confluence page created")
        return {"status": "success"}
