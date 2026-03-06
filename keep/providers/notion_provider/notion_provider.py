"""Notion workspace provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class NotionProviderAuthConfig:
    integration_token: str = dataclasses.field(
        metadata={"required": True, "description": "Notion Integration Token", "sensitive": True},
        default=""
    )

class NotionProvider(BaseProvider):
    """Notion workspace provider."""
    
    PROVIDER_DISPLAY_NAME = "Notion"
    PROVIDER_CATEGORY = ["Collaboration"]
    NOTION_API = "https://api.notion.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NotionProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, page_id: str = "", text: str = "", **kwargs: Dict[str, Any]):
        if not page_id or not text:
            raise ProviderException("Page ID and text are required")

        payload = {
            "parent": {"page_id": page_id},
            "properties": {
                "title": [{"text": {"content": text}}]
            }
        }

        try:
            response = requests.post(
                f"{self.NOTION_API}/pages",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.integration_token}",
                    "Notion-Version": "2022-06-28",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Notion API error: {e}")

        self.logger.info("Notion page created")
        return {"status": "success"}
