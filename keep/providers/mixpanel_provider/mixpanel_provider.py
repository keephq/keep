"""Mixpanel Analytics provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MixpanelProviderAuthConfig:
    project_token: str = dataclasses.field(
        metadata={"required": True, "description": "Mixpanel Project Token", "sensitive": True},
        default=""
    )

class MixpanelProvider(BaseProvider):
    """Mixpanel Analytics provider."""
    
    PROVIDER_DISPLAY_NAME = "Mixpanel"
    PROVIDER_CATEGORY = ["Analytics"]
    MIXPANEL_API = "https://api.mixpanel.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MixpanelProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, event: str = "", distinct_id: str = "", properties: Dict = None, **kwargs: Dict[str, Any]):
        if not event or not distinct_id:
            raise ProviderException("Event and distinct_id are required")

        payload = [{
            "event": event,
            "properties": {
                "token": self.authentication_config.project_token,
                "distinct_id": distinct_id,
                **(properties or {})
            }
        }]

        try:
            response = requests.post(
                f"{self.MIXPANEL_API}/track",
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Mixpanel API error: {e}")

        self.logger.info("Mixpanel event tracked")
        return {"status": "success"}
