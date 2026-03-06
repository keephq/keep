"""Twitch streaming provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TwitchProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Twitch Client ID"},
        default=""
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Twitch Access Token", "sensitive": True},
        default=""
    )

class TwitchProvider(BaseProvider):
    """Twitch streaming provider."""
    
    PROVIDER_DISPLAY_NAME = "Twitch"
    PROVIDER_CATEGORY = ["Gaming"]
    TWITCH_API = "https://api.twitch.tv/helix"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TwitchProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, broadcaster_id: str = "", title: str = "", **kwargs: Dict[str, Any]):
        if not broadcaster_id or not title:
            raise ProviderException("Broadcaster ID and title are required")

        payload = {
            "broadcaster_id": broadcaster_id,
            "title": title
        }

        try:
            response = requests.post(
                f"{self.TWITCH_API}/channel",
                json=payload,
                headers={
                    "Client-ID": self.authentication_config.client_id,
                    "Authorization": f"Bearer {self.authentication_config.access_token}"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Twitch API error: {e}")

        self.logger.info("Twitch channel updated")
        return {"status": "success"}
