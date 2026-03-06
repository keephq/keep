"""Pushover Tech SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PushoverTechProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Pushover API Key", "sensitive": True},
        default=""
    )
    user_key: str = dataclasses.field(
        metadata={"required": True, "description": "Pushover User Key", "sensitive": True},
        default=""
    )

class PushoverTechProvider(BaseProvider):
    """Pushover push notification provider."""
    
    PROVIDER_DISPLAY_NAME = "Pushover Tech"
    PROVIDER_CATEGORY = ["Notifications"]
    PUSHOVER_API = "https://api.pushover.net/1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PushoverTechProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", title: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "token": self.authentication_config.api_key,
            "user": self.authentication_config.user_key,
            "message": message,
            "title": title
        }

        try:
            response = requests.post(
                f"{self.PUSHOVER_API}/messages.json",
                data=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Pushover API error: {e}")

        self.logger.info("Pushover notification sent")
        return {"status": "success"}
