"""Clickatell SMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ClickatellProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Clickatell API Key", "sensitive": True},
        default=""
    )

class ClickatellProvider(BaseProvider):
    """Clickatell SMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Clickatell"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    
    CLICKATELL_API = "https://platform.clickatell.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ClickatellProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        payload = {
            "to": [to],
            "content": message
        }

        try:
            response = requests.post(
                f"{self.CLICKATELL_API}/v1/message",
                json=payload,
                headers={"Authorization": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Clickatell API error: {e}")

        self.logger.info("SMS sent via Clickatell")
        return {"status": "success"}
