"""Google Analytics provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GAProviderAuthConfig:
    measurement_id: str = dataclasses.field(
        metadata={"required": True, "description": "GA4 Measurement ID"},
        default=""
    )
    api_secret: str = dataclasses.field(
        metadata={"required": True, "description": "API Secret", "sensitive": True},
        default=""
    )

class GAProvider(BaseProvider):
    """Google Analytics provider."""
    
    PROVIDER_DISPLAY_NAME = "Google Analytics"
    PROVIDER_CATEGORY = ["Analytics"]
    GA_API = "https://www.google-analytics.com/mp/collect"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GAProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, client_id: str = "", events: list = None, **kwargs: Dict[str, Any]):
        if not client_id or not events:
            raise ProviderException("Client ID and events are required")

        payload = {
            "client_id": client_id,
            "events": events
        }

        try:
            response = requests.post(
                f"{self.GA_API}?measurement_id={self.authentication_config.measurement_id}&api_secret={self.authentication_config.api_secret}",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Google Analytics API error: {e}")

        self.logger.info("Google Analytics event tracked")
        return {"status": "success"}
