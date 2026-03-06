"""ClickUp project management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ClickUpProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "ClickUp API Token", "sensitive": True},
        default=""
    )

class ClickUpProvider(BaseProvider):
    """ClickUp project management provider."""
    
    PROVIDER_DISPLAY_NAME = "ClickUp"
    PROVIDER_CATEGORY = ["Project Management"]
    CLICKUP_API = "https://api.clickup.com/api/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ClickUpProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, list_id: str = "", name: str = "", description: str = "", **kwargs: Dict[str, Any]):
        if not list_id or not name:
            raise ProviderException("List ID and name are required")

        payload = {
            "name": name,
            "description": description
        }

        try:
            response = requests.post(
                f"{self.CLICKUP_API}/list/{list_id}/task",
                json=payload,
                headers={
                    "Authorization": self.authentication_config.api_token,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"ClickUp API error: {e}")

        self.logger.info(f"ClickUp task created: {name}")
        return {"status": "success", "name": name}
