"""Firebase Cloud Messaging provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FCMProviderAuthConfig:
    server_key: str = dataclasses.field(
        metadata={"required": True, "description": "FCM Server Key", "sensitive": True},
        default=""
    )

class FCMProvider(BaseProvider):
    """Firebase Cloud Messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Firebase Cloud Messaging"
    PROVIDER_CATEGORY = ["Notifications"]
    FCM_API = "https://fcm.googleapis.com/fcm"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FCMProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", title: str = "", body: str = "", **kwargs: Dict[str, Any]):
        if not to or not body:
            raise ProviderException("To and body are required")

        payload = {
            "to": to,
            "notification": {
                "title": title,
                "body": body
            }
        }

        try:
            response = requests.post(
                f"{self.FCM_API}/send",
                json=payload,
                headers={
                    "Authorization": f"key={self.authentication_config.server_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"FCM API error: {e}")

        self.logger.info("FCM notification sent")
        return {"status": "success"}
