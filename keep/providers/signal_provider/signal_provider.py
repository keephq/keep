"""Signal messaging provider via Signal CLI REST API."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SignalProviderAuthConfig:
    api_url: str = dataclasses.field(
        metadata={"required": True, "description": "Signal CLI REST API URL"},
        default=""
    )
    phone_number: str = dataclasses.field(
        metadata={"required": True, "description": "Signal Phone Number"},
        default=""
    )

class SignalProvider(BaseProvider):
    """Signal messaging provider."""
    
    PROVIDER_DISPLAY_NAME = "Signal"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SignalProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        payload = {
            "message": message,
            "number": self.authentication_config.phone_number,
            "recipients": [to]
        }

        try:
            response = requests.post(
                f"{self.authentication_config.api_url}/v2/send",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Signal API error: {e}")

        self.logger.info("Signal message sent")
        return {"status": "success"}
