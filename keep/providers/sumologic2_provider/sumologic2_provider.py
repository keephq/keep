"""Sumo Logic logging provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SumoLogic2ProviderAuthConfig:
    endpoint_url: str = dataclasses.field(
        metadata={"required": True, "description": "Sumo Logic HTTP Source URL", "sensitive": True},
        default=""
    )

class SumoLogic2Provider(BaseProvider):
    """Sumo Logic logging provider."""
    
    PROVIDER_DISPLAY_NAME = "Sumo Logic"
    PROVIDER_CATEGORY = ["Logging"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SumoLogic2ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        try:
            response = requests.post(
                self.authentication_config.endpoint_url,
                data=message,
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Sumo Logic API error: {e}")

        self.logger.info("Sumo Logic log sent")
        return {"status": "success"}
