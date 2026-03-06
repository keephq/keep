"""Discord Webhook provider (simplified)."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DiscordWebhookProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Discord Webhook URL", "sensitive": True},
        default=""
    )

class DiscordWebhookProvider(BaseModel):
    """Discord Webhook provider (simplified)."""
    
    PROVIDER_DISPLAY_NAME = "Discord Webhook"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DiscordWebhookProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, content: str = "", **kwargs: Dict[str, Any]):
        if not content:
            raise ProviderException("Content is required")

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json={"content": content},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Discord Webhook error: {e}")

        self.logger.info("Discord message sent via webhook")
        return {"status": "success"}
