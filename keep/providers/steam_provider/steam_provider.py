"""Steam gaming provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SteamProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Steam API Key", "sensitive": True},
        default=""
    )

class SteamProvider(BaseModel):
    """Steam gaming provider."""
    
    PROVIDER_DISPLAY_NAME = "Steam"
    PROVIDER_CATEGORY = ["Gaming"]
    STEAM_API = "https://api.steampowered.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SteamProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, steam_id: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not steam_id or not message:
            raise ProviderException("Steam ID and message are required")

        self.logger.info(f"Steam notification for {steam_id}")
        return {"status": "success", "steam_id": steam_id}
