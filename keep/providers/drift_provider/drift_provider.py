"""Drift conversational marketing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DriftProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Drift Access Token", "sensitive": True},
        default=""
    )

class DriftProvider(BaseProvider):
    """Drift conversational marketing provider."""
    
    PROVIDER_DISPLAY_NAME = "Drift"
    PROVIDER_CATEGORY = ["Customer Support"]
    DRIFT_API = "https://driftapi.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DriftProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, contact_id: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not contact_id or not message:
            raise ProviderException("Contact ID and message are required")

        payload = {
            "type": "message",
            "body": message,
            "contactId": contact_id
        }

        try:
            response = requests.post(
                f"{self.DRIFT_API}/conversations",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Drift API error: {e}")

        self.logger.info(f"Drift message sent to contact: {contact_id}")
        return {"status": "success", "contact_id": contact_id}
