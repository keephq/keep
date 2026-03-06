"""Amplitude Analytics provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AmplitudeProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Amplitude API Key", "sensitive": True},
        default=""
    )

class AmplitudeProvider(BaseProvider):
    """Amplitude Analytics provider."""
    
    PROVIDER_DISPLAY_NAME = "Amplitude"
    PROVIDER_CATEGORY = ["Analytics"]
    AMPLITUDE_API = "https://api.amplitude.com/2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AmplitudeProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, event_type: str = "", user_id: str = "", event_properties: Dict = None, **kwargs: Dict[str, Any]):
        if not event_type or not user_id:
            raise ProviderException("Event type and user_id are required")

        payload = {
            "api_key": self.authentication_config.api_key,
            "events": [{
                "event_type": event_type,
                "user_id": user_id,
                "event_properties": event_properties or {}
            }]
        }

        try:
            response = requests.post(
                f"{this.AMPLITUDE_API}/httpapi",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Amplitude API error: {e}")

        self.logger.info("Amplitude event tracked")
        return {"status": "success"}
