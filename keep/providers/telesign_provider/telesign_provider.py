"""Telesign SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TelesignProviderAuthConfig:
    customer_id: str = dataclasses.field(
        metadata={"required": True, "description": "Telesign Customer ID"},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Telesign API Key", "sensitive": True},
        default=""
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "From Phone Number"},
        default=""
    )

class TelesignProvider(BaseProvider):
    """Telesign SMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Telesign"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    TELESIGN_API = "https://rest-api.telesign.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TelesignProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        payload = {
            "phone_number": to,
            "message": message,
            "message_type": "ARN"
        }

        try:
            response = requests.post(
                f"{self.TELESIGN_API}/v1/messaging",
                json=payload,
                auth=(self.authentication_config.customer_id, self.authentication_config.api_key),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Telesign API error: {e}")

        self.logger.info("SMS sent via Telesign")
        return {"status": "success"}
