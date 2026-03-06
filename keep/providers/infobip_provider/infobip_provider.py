"""InfoBip Voice provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class InfoBipProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "InfoBip API Key", "sensitive": True},
        default=""
    )
    base_url: str = dataclasses.field(
        metadata={"required": True, "description": "InfoBip Base URL"},
        default="https://api.infobip.com"
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "From Phone Number"},
        default=""
    )

class InfoBipProvider(BaseProvider):
    """InfoBip Voice provider."""
    
    PROVIDER_DISPLAY_NAME = "InfoBip"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["voice", "phone"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = InfoBipProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        payload = {
            "from": self.authentication_config.from_number,
            "to": to,
            "text": message
        }

        try:
            response = requests.post(
                f"{self.authentication_config.base_url}/tts/3/single",
                json=payload,
                headers={"Authorization": f"App {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"InfoBip API error: {e}")

        self.logger.info("Voice call initiated via InfoBip")
        return {"status": "success"}
