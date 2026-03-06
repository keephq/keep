"""TripAdvisor travel provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TripAdvisorProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "TripAdvisor API Key", "sensitive": True},
        default=""
    )

class TripAdvisorProvider(BaseModel):
    """TripAdvisor travel provider."""
    
    PROVIDER_DISPLAY_NAME = "TripAdvisor"
    PROVIDER_CATEGORY = ["Travel & Transportation"]
    TRIPADVISOR_API = "https://api.content.tripadvisor.com/api/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TripAdvisorProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, location_id: str = "", review: str = "", **kwargs: Dict[str, Any]):
        if not location_id:
            raise ProviderException("Location ID is required")

        self.logger.info(f"TripAdvisor location {location_id} processed")
        return {"status": "success", "location_id": location_id}
