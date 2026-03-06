"""Dexcom voice notification provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DexcomProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Dexcom API Key", "sensitive": True},
        default=""
    )
    phone_number: str = dataclasses.field(
        metadata={"required": True, "description": "Phone Number"},
        default=""
    )

class DexcomProvider(BaseProvider):
    """Dexcom voice notification provider."""
    
    PROVIDER_DISPLAY_NAME = "Dexcom"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["voice"]
    DEXCOM_API = "https://api.dexcom.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DexcomProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "phone_number": self.authentication_config.phone_number,
            "message": message
        }

        try:
            response = requests.post(
                f"{self.DEXCOM_API}/v1/voice/call",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Dexcom API error: {e}")

        self.logger.info("Voice call initiated via Dexcom")
        return {"status": "success"}
