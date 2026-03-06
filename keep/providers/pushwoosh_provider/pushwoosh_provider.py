"""Pushwoosh push notification provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PushwooshProviderAuthConfig:
    application_code: str = dataclasses.field(
        metadata={"required": True, "description": "Pushwoosh Application Code"},
        default=""
    )
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Pushwoosh API Token", "sensitive": True},
        default=""
    )

class PushwooshProvider(BaseProvider):
    """Pushwoosh push notification provider."""
    
    PROVIDER_DISPLAY_NAME = "Pushwoosh"
    PROVIDER_CATEGORY = ["Notifications"]
    PUSHWOOSH_API = "https://cp.pushwoosh.com/json/1.3"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PushwooshProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, content: str = "", **kwargs: Dict[str, Any]):
        if not content:
            raise ProviderException("Content is required")

        payload = {
            "request": {
                "application": self.authentication_config.application_code,
                "auth": self.authentication_config.api_token,
                "notifications": [{
                    "send_date": "now",
                    "content": content
                }]
            }
        }

        try:
            response = requests.post(
                f"{self.PUSHWOOSH_API}/createMessage",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Pushwoosh API error: {e}")

        self.logger.info("Pushwoosh notification sent")
        return {"status": "success"}
