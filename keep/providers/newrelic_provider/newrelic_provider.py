"""New Relic monitoring provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class NewRelicProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "New Relic API Key", "sensitive": True},
        default=""
    )

class NewRelicProvider(BaseProvider):
    """New Relic monitoring provider."""
    
    PROVIDER_DISPLAY_NAME = "New Relic"
    PROVIDER_CATEGORY = ["Monitoring"]
    NEWRELIC_API = "https://api.newrelic.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NewRelicProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {"event": {"message": message}}

        try:
            response = requests.post(
                f"{self.NEWRELIC_API}/events",
                json=payload,
                headers={"X-Api-Key": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"New Relic API error: {e}")

        self.logger.info("New Relic event created")
        return {"status": "success"}
