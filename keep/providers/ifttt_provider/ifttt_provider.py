"""IFTTT automation provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class IFTTTProviderAuthConfig:
    webhook_key: str = dataclasses.field(
        metadata={"required": True, "description": "IFTTT Webhook Key", "sensitive": True},
        default=""
    )

class IFTTTProvider(BaseProvider):
    """IFTTT automation provider."""
    
    PROVIDER_DISPLAY_NAME = "IFTTT"
    PROVIDER_CATEGORY = ["Automation"]
    IFTTT_API = "https://maker.ifttt.com/trigger"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = IFTTTProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, event: str = "", value1: str = "", value2: str = "", value3: str = "", **kwargs: Dict[str, Any]):
        if not event:
            raise ProviderException("Event name is required")

        payload = {
            "value1": value1,
            "value2": value2,
            "value3": value3
        }

        try:
            response = requests.post(
                f"{self.IFTTT_API}/{event}/with/key/{self.authentication_config.webhook_key}",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"IFTTT API error: {e}")

        self.logger.info(f"IFTTT event triggered: {event}")
        return {"status": "success", "event": event}
