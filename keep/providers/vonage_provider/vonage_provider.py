"""Vonage (Nexmo) SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VonageProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Vonage API Key"},
        default=""
    )
    api_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Vonage API Secret", "sensitive": True},
        default=""
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "From Phone Number"},
        default=""
    )

class VonageProvider(BaseProvider):
    """Vonage (Nexmo) SMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Vonage"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    VONAGE_API = "https://rest.nexmo.com/sms/json"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VonageProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", text: str = "", **kwargs: Dict[str, Any]):
        if not to or not text:
            raise ProviderException("To and text are required")

        payload = {
            "api_key": self.authentication_config.api_key,
            "api_secret": self.authentication_config.api_secret,
            "from": self.authentication_config.from_number,
            "to": to,
            "text": text
        }

        try:
            response = requests.post(
                self.VONAGE_API,
                data=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Vonage API error: {e}")

        self.logger.info("SMS sent via Vonage")
        return {"status": "success"}
