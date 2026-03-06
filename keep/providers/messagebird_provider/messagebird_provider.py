"""MessageBird SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MessageBirdProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "MessageBird API Key", "sensitive": True},
        default=""
    )
    originator: str = dataclasses.field(
        metadata={"required": True, "description": "Sender ID or Phone Number"},
        default=""
    )

class MessageBirdProvider(BaseProvider):
    """MessageBird SMS provider."""
    
    PROVIDER_DISPLAY_NAME = "MessageBird"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    MESSAGEBIRD_API = "https://rest.messagebird.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MessageBirdProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, recipients: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not recipients or not message:
            raise ProviderException("Recipients and message are required")

        payload = {
            "originator": self.authentication_config.originator,
            "recipients": recipients,
            "body": message
        }

        try:
            response = requests.post(
                f"{self.MESSAGEBIRD_API}/messages",
                data=payload,
                headers={"Authorization": f"AccessKey {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"MessageBird API error: {e}")

        self.logger.info("SMS sent via MessageBird")
        return {"status": "success"}
