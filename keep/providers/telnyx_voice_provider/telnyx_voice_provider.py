"""Telnyx Voice provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TelnyxVoiceProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Telnyx API Key", "sensitive": True},
        default=""
    )
    connection_id: str = dataclasses.field(
        metadata={"required": True, "description": "Telnyx Connection ID"},
        default=""
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "From Phone Number"},
        default=""
    )

class TelnyxVoiceProvider(BaseProvider):
    """Telnyx Voice provider."""
    
    PROVIDER_DISPLAY_NAME = "Telnyx Voice"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["voice", "phone"]
    TELNYX_API = "https://api.telnyx.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TelnyxVoiceProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        payload = {
            "to": to,
            "from": self.authentication_config.from_number,
            "connection_id": self.authentication_config.connection_id,
            "audio_url": f"data:audio/wav;base64,{message}"  # Simplified
        }

        try:
            response = requests.post(
                f"{self.TELNYX_API}/calls",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Telnyx Voice API error: {e}")

        self.logger.info("Phone call initiated via Telnyx")
        return {"status": "success"}
