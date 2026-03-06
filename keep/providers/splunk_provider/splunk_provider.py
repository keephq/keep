"""Splunk monitoring provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SplunkProviderAuthConfig:
    token: str = dataclasses.field(
        metadata={"required": True, "description": "Splunk Token", "sensitive": True},
        default=""
    )
    host: str = dataclasses.field(
        metadata={"required": True, "description": "Splunk Host URL"},
        default=""
    )
    index: str = dataclasses.field(
        metadata={"required": True, "description": "Splunk Index"},
        default="main"
    )

class SplunkProvider(BaseProvider):
    """Splunk monitoring provider."""
    
    PROVIDER_DISPLAY_NAME = "Splunk"
    PROVIDER_CATEGORY = ["Monitoring"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SplunkProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, event: str = "", **kwargs: Dict[str, Any]):
        if not event:
            raise ProviderException("Event is required")

        payload = {
            "index": self.authentication_config.index,
            "event": event
        }

        try:
            response = requests.post(
                f"{self.authentication_config.host}/services/collector",
                json=payload,
                headers={"Authorization": f"Splunk {self.authentication_config.token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Splunk API error: {e}")

        self.logger.info("Splunk event created")
        return {"status": "success"}
