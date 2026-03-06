"""Plivo SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PlivoProviderAuthConfig:
    auth_id: str = dataclasses.field(
        metadata={"required": True, "description": "Plivo Auth ID"},
        default=""
    )
    auth_token: str = dataclasses.field(
        metadata={"required": True, "description": "Plivo Auth Token", "sensitive": True},
        default=""
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "From Phone Number"},
        default=""
    )

class PlivoProvider(BaseProvider):
    """Plivo SMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Plivo"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    PLIVO_API = "https://api.plivo.com/v1/Account"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PlivoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", text: str = "", **kwargs: Dict[str, Any]):
        if not to or not text:
            raise ProviderException("To and text are required")

        payload = {
            "src": self.authentication_config.from_number,
            "dst": to,
            "text": text
        }

        try:
            response = requests.post(
                f"{self.PLIVO_API}/{self.authentication_config.auth_id}/Message/",
                json=payload,
                auth=(self.authentication_config.auth_id, self.authentication_config.auth_token),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Plivo API error: {e}")

        self.logger.info("SMS sent via Plivo")
        return {"status": "success"}
