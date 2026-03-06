"""46elks SMS provider for EU market."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ElksProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "46elks API Key", "sensitive": True},
        default=""
    )
    api_secret: str = dataclasses.field(
        metadata={"required": True, "description": "46elks API Secret", "sensitive": True},
        default=""
    )
    from_number: str = dataclasses.field(
        metadata={"required": True, "description": "From Phone Number"},
        default=""
    )

class ElksProvider(BaseProvider):
    """46elks SMS provider for EU market."""
    
    PROVIDER_DISPLAY_NAME = "46elks"
    PROVIDER_CATEGORY = ["Notifications"]
    PROVIDER_TAGS = ["sms"]
    ELKS_API = "https://api.46elks.com/a1/sms"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ElksProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, to: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not to or not message:
            raise ProviderException("To and message are required")

        payload = {
            "from": self.authentication_config.from_number,
            "to": to,
            "message": message
        }

        try:
            response = requests.post(
                self.ELKS_API,
                data=payload,
                auth=(self.authentication_config.api_key, self.authentication_config.api_secret),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"46elks API error: {e}")

        self.logger.info("SMS sent via 46elks")
        return {"status": "success"}
