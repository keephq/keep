"""Dribbble design community provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DribbbleProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Dribbble Access Token", "sensitive": True},
        default=""
    )

class DribbbleProvider(BaseProvider):
    """Dribbble design community provider."""
    
    PROVIDER_DISPLAY_NAME = "Dribbble"
    PROVIDER_CATEGORY = ["Design & Creative"]
    DRIBBBLE_API = "https://api.dribbble.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DribbbleProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, shot_id: str = "", title: str = "", description: str = "", **kwargs: Dict[str, Any]):
        if not shot_id:
            raise ProviderException("Shot ID is required")

        try:
            response = requests.get(
                f"{self.DRIBBBLE_API}/shots/{shot_id}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Dribbble API error: {e}")

        self.logger.info(f"Dribbble shot retrieved: {shot_id}")
        return {"status": "success", "shot_id": shot_id}
