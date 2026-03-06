"""Loggly logging provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LogglyProviderAuthConfig:
    token: str = dataclasses.field(
        metadata={"required": True, "description": "Loggly Token", "sensitive": True},
        default=""
    )

class LogglyProvider(BaseProvider):
    """Loggly logging provider."""
    
    PROVIDER_DISPLAY_NAME = "Loggly"
    PROVIDER_CATEGORY = ["Logging"]
    LOGGLY_API = "https://logs-01.loggly.com/inputs"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LogglyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        try:
            response = requests.post(
                f"{self.LOGGLY_API}/{self.authentication_config.token}",
                json={"message": message},
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Loggly API error: {e}")

        self.logger.info("Loggly event sent")
        return {"status": "success"}
