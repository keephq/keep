"""Dynatrace monitoring provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DynatraceProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Dynatrace API Token", "sensitive": True},
        default=""
    )
    environment_url: str = dataclasses.field(
        metadata={"required": True, "description": "Dynatrace Environment URL"},
        default=""
    )

class DynatraceProvider(BaseProvider):
    """Dynatrace monitoring provider."""
    
    PROVIDER_DISPLAY_NAME = "Dynatrace"
    PROVIDER_CATEGORY = ["Monitoring"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DynatraceProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {"message": message}

        try:
            response = requests.post(
                f"{self.authentication_config.environment_url}/api/v1/events",
                json=payload,
                headers={"Authorization": f"Api-Token {self.authentication_config.api_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Dynatrace API error: {e}")

        self.logger.info("Dynatrace event created")
        return {"status": "success"}
