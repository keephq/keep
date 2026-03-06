"""Slack Webhook provider (simplified)."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SlackWebhookProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Slack Webhook URL", "sensitive": True},
        default=""
    )

class SlackWebhookProvider(BaseModel):
    """Slack Webhook provider (simplified)."""
    
    PROVIDER_DISPLAY_NAME = "Slack Webhook"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SlackWebhookProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, text: str = "", **kwargs: Dict[str, Any]):
        if not text:
            raise ProviderException("Text is required")

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json={"text": text},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Slack Webhook error: {e}")

        self.logger.info("Slack message sent via webhook")
        return {"status": "success"}
