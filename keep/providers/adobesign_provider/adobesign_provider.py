"""Adobe Sign e-signature provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AdobeSignProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Adobe Sign Access Token", "sensitive": True},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Adobe Sign API Key"},
        default=""
    )

class AdobeSignProvider(BaseProvider):
    """Adobe Sign e-signature provider."""
    
    PROVIDER_DISPLAY_NAME = "Adobe Sign"
    PROVIDER_CATEGORY = ["Legal & Compliance"]
    ADOBESIGN_API = "https://api.na1.adobesign.com/api/rest/v6"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AdobeSignProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, agreement_id: str = "", **kwargs: Dict[str, Any]):
        if not agreement_id:
            raise ProviderException("Agreement ID is required")

        try:
            response = requests.get(
                f"{self.ADOBESIGN_API}/agreements/{agreement_id}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "x-api-key": self.authentication_config.api_key,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Adobe Sign API error: {e}")

        self.logger.info(f"Adobe Sign agreement retrieved: {agreement_id}")
        return {"status": "success", "agreement_id": agreement_id}
