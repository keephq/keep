"""Trello project management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TrelloProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Trello API Key"},
        default=""
    )
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Trello API Token", "sensitive": True},
        default=""
    )

class TrelloProvider(BaseModel):
    """Trello project management provider."""
    
    PROVIDER_DISPLAY_NAME = "Trello"
    PROVIDER_CATEGORY = ["Collaboration"]
    TRELLO_API = "https://api.trello.com/1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TrelloProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, list_id: str = "", name: str = "", desc: str = "", **kwargs: Dict[str, Any]):
        if not list_id or not name:
            raise ProviderException("List ID and name are required")

        params = {
            "key": self.authentication_config.api_key,
            "token": self.authentication_config.api_token,
            "name": name,
            "desc": desc or name,
            "idList": list_id
        }

        try:
            response = requests.post(
                f"{self.TRELLO_API}/cards",
                params=params,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Trello API error: {e}")

        self.logger.info("Trello card created")
        return {"status": "success"}
