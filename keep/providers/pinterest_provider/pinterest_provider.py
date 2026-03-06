"""Pinterest social media provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PinterestProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Pinterest Access Token", "sensitive": True},
        default=""
    )

class PinterestProvider(BaseProvider):
    """Pinterest social media provider."""
    
    PROVIDER_DISPLAY_NAME = "Pinterest"
    PROVIDER_CATEGORY = ["Social Media"]
    PINTEREST_API = "https://api.pinterest.com/v5"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PinterestProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, board_id: str = "", note: str = "", **kwargs: Dict[str, Any]):
        if not board_id:
            raise ProviderException("Board ID is required")

        try:
            response = requests.post(
                f"{self.PINTEREST_API}/boards/{board_id}/pins",
                json={"note": note},
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Pinterest API error: {e}")

        self.logger.info(f"Pinterest pin created on board {board_id}")
        return {"status": "success", "board_id": board_id}
