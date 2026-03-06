"""Notion Template provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class NotionTemplateProviderAuthConfig:
    access_token: str = dataclasses.field(metadata={"required": True, "description": "Notion Access Token", "sensitive": True}, default="")

class NotionTemplateProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Notion Template"
    PROVIDER_CATEGORY = ["Productivity"]
    NOTION_API = "https://api.notion.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NotionTemplateProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, page_id: str = "", **kwargs: Dict[str, Any]):
        if not page_id:
            raise ProviderException("Page ID is required")
        self.logger.info(f"Notion template used: {page_id}")
        return {"status": "success", "page_id": page_id}
