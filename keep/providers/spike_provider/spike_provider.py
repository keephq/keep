"""Spike.sh incident provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SpikeProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Spike.sh API Key", "sensitive": True},
        default=""
    )

class SpikeProvider(BaseProvider):
    """Spike.sh incident management provider."""
    
    PROVIDER_DISPLAY_NAME = "Spike.sh"
    PROVIDER_CATEGORY = ["Incident Management"]
    SPIKE_API = "https://api.spike.sh/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SpikeProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, title: str = "", message: str = "", priority: str = "high", **kwargs: Dict[str, Any]):
        if not title:
            raise ProviderException("Title is required")

        payload = {
            "title": title,
            "message": message,
            "priority": priority
        }

        try:
            response = requests.post(
                f"{self.SPIKE_API}/incidents",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Spike.sh API error: {e}")

        self.logger.info("Spike.sh incident created")
        return {"status": "success"}
