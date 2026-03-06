"""LinkedIn social media provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LinkedInProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "LinkedIn Access Token", "sensitive": True},
        default=""
    )

class LinkedInProvider(BaseModel):
    """LinkedIn social media provider."""
    
    PROVIDER_DISPLAY_NAME = "LinkedIn"
    PROVIDER_CATEGORY = ["Social Media"]
    LINKEDIN_API = "https://api.linkedin.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LinkedInProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, text: str = "", **kwargs: Dict[str, Any]):
        if not text:
            raise ProviderException("Text is required")

        payload = {"text": text}

        try:
            response = requests.post(
                f"{self.LINKEDIN_API}/shares",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"LinkedIn API error: {e}")

        self.logger.info("LinkedIn post shared")
        return {"status": "success"}
