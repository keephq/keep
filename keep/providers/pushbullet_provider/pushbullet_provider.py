"""Pushbullet push notification provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PushbulletProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Pushbullet API Key", "sensitive": True},
        default=""
    )

class PushbulletProvider(BaseProvider):
    """Pushbullet push notification provider."""
    
    PROVIDER_DISPLAY_NAME = "Pushbullet"
    PROVIDER_CATEGORY = ["Notifications"]
    PUSHBULLET_API = "https://api.pushbullet.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PushbulletProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, title: str = "", body: str = "", **kwargs: Dict[str, Any]):
        if not body:
            raise ProviderException("Body is required")

        payload = {"type": "note", "title": title, "body": body}

        try:
            response = requests.post(
                f"{self.PUSHBULLET_API}/pushes",
                json=payload,
                headers={"Access-Token": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Pushbullet API error: {e}")

        self.logger.info("Pushbullet notification sent")
        return {"status": "success"}
