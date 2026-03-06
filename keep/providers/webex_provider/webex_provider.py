"""Webex Teams provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WebexProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Webex Access Token", "sensitive": True},
        default=""
    )
    room_id: str = dataclasses.field(
        metadata={"required": True, "description": "Webex Room ID"},
        default=""
    )

class WebexProvider(BaseProvider):
    """Webex Teams messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Webex"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]
    WEBEX_API = "https://webexapis.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WebexProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, text: str = "", **kwargs: Dict[str, Any]):
        if not text:
            raise ProviderException("Text is required")

        payload = {
            "roomId": self.authentication_config.room_id,
            "text": text
        }

        try:
            response = requests.post(
                f"{self.WEBEX_API}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Webex API error: {e}")

        self.logger.info("Webex message sent")
        return {"status": "success"}
