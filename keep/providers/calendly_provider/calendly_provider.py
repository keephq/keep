"""Calendly scheduling provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class CalendlyProviderAuthConfig:
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Calendly API Key", "sensitive": True}, default="")

class CalendlyProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Calendly"
    PROVIDER_CATEGORY = ["Scheduling"]
    CALENDLY_API = "https://api.calendly.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CalendlyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, event_uuid: str = "", **kwargs: Dict[str, Any]):
        if not event_uuid:
            raise ProviderException("Event UUID is required")
        try:
            response = requests.get(
                f"{self.CALENDLY_API}/scheduled_events/{event_uuid}",
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Calendly API error: {e}")
        self.logger.info(f"Calendly event retrieved: {event_uuid}")
        return {"status": "success", "event_uuid": event_uuid}
