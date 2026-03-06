"""Intercom customer messaging provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class IntercomProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Intercom Access Token", "sensitive": True},
        default=""
    )

class IntercomProvider(BaseProvider):
    """Intercom customer messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Intercom"
    PROVIDER_CATEGORY = ["Customer Support"]
    INTERCOM_API = "https://api.intercom.io"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = IntercomProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, user_id: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not user_id or not message:
            raise ProviderException("User ID and message are required")

        payload = {
            "message_type": "inapp",
            "type": "email",
            "subject": kwargs.get("subject", "Notification"),
            "body": message,
            "from": {"type": "admin", "id": kwargs.get("admin_id", "")},
            "to": {"type": "user", "id": user_id}
        }

        try:
            response = requests.post(
                f"{self.INTERCOM_API}/messages",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Intercom API error: {e}")

        self.logger.info(f"Intercom message sent to user: {user_id}")
        return {"status": "success", "user_id": user_id}
