"""SNS SMS provider for India market."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SNSSMSProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "SNS API Key", "sensitive": True},
        default=""
    )
    sender_id: str = dataclasses.field(
        metadata={"required": True, "description": "Sender ID"},
        default=""
    )

class SNSSMSProvider(BaseProvider):
    """SNS SMS provider for India market."""
    
    PROVIDER_DISPLAY_NAME = "SNS SMS"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    SNS_API = "https://api.snsindia.in"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SNSSMSProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        payload = {
            "apikey": self.authentication_config.api_key,
            "sender": self.authentication_config.sender_id,
            "to": to,
            "message": message
        }

        try:
            response = requests.post(
                f"{self.SNS_API}/api/v3/send-sms",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"SNS SMS API error: {e}")

        self.logger.info("SMS sent via SNS")
        return {"status": "success"}
