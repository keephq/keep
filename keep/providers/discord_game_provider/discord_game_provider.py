"""Discord Game Activity provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DiscordGameProviderAuthConfig:
    bot_token: str = dataclasses.field(
        metadata={"required": True, "description": "Discord Bot Token", "sensitive": True},
        default=""
    )

class DiscordGameProvider(BaseProvider):
    """Discord Game Activity provider."""
    
    PROVIDER_DISPLAY_NAME = "Discord Game"
    PROVIDER_CATEGORY = ["Gaming"]
    DISCORD_API = "https://discord.com/api/v10"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DiscordGameProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, channel_id: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not channel_id or not message:
            raise ProviderException("Channel ID and message are required")

        payload = {"content": message}

        try:
            response = requests.post(
                f"{self.DISCORD_API}/channels/{channel_id}/messages",
                json=payload,
                headers={"Authorization": f"Bot {self.authentication_config.bot_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Discord API error: {e}")

        self.logger.info("Discord game message sent")
        return {"status": "success"}
