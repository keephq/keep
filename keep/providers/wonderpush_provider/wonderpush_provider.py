"""WonderPush push notification provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WonderPushProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "WonderPush Access Token", "sensitive": True},
        default=""
    )

class WonderPushProvider(BaseProvider):
    """WonderPush push notification provider."""
    
    PROVIDER_DISPLAY_NAME = "WonderPush"
    PROVIDER_CATEGORY = ["Notifications"]
    WONDERPUSH_API = "https://api.wonderpush.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WonderPushProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, title: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "payload": {
                "title": title,
                "message": message
            }
        }

        try:
            response = requests.post(
                f"{self.WONDERPUSH_API}/deliveries",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"WonderPush API error: {e}")

        self.logger.info("WonderPush notification sent")
        return {"status": "success"}
