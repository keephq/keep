"""Mattermost provider for team messaging."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MattermostProviderAuthConfig:
    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Mattermost Webhook URL", "sensitive": True},
        default=""
    )

class MattermostProvider(BaseProvider):
    """Mattermost team messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Mattermost"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MattermostProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, text: str = "", username: str = "", channel: str = "", **kwargs: Dict[str, Any]):
        if not text:
            raise ProviderException("Text is required")

        payload = {"text": text}
        if username:
            payload["username"] = username
        if channel:
            payload["channel"] = channel

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Mattermost API error: {e}")

        self.logger.info("Mattermost message sent")
        return {"status": "success"}
