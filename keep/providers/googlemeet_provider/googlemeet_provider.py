"""Google Meet video conferencing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GoogleMeetProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Google Meet Access Token", "sensitive": True},
        default=""
    )

class GoogleMeetProvider(BaseProvider):
    """Google Meet video conferencing provider."""
    
    PROVIDER_DISPLAY_NAME = "Google Meet"
    PROVIDER_CATEGORY = ["Video Conferencing"]
    GOOGLEMEET_API = "https://meet.googleapis.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GoogleMeetProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, conference_id: str = "", summary: str = "", **kwargs: Dict[str, Any]):
        if not conference_id:
            raise ProviderException("Conference ID is required")

        try:
            response = requests.get(
                f"{self.GOOGLEMEET_API}/conferences/{conference_id}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Google Meet API error: {e}")

        self.logger.info(f"Google Meet conference retrieved: {conference_id}")
        return {"status": "success", "conference_id": conference_id}
