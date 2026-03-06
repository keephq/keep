"""Opsgenie provider for alert management."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class OpsgenieProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Opsgenie API Key", "sensitive": True},
        default=""
    )

class OpsgenieProvider(BaseProvider):
    """Opsgenie alert management provider."""
    
    PROVIDER_DISPLAY_NAME = "Opsgenie"
    PROVIDER_CATEGORY = ["Incident Management"]
    OPSGENIE_API = "https://api.opsgenie.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = OpsgenieProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, message: str = "", priority: str = "P3", **kwargs: Dict[str, Any]):
        if not message:
            raise ProviderException("Message is required")

        payload = {
            "message": message,
            "priority": priority
        }

        try:
            response = requests.post(
                f"{self.OPSGENIE_API}/v2/alerts",
                json=payload,
                headers={"Authorization": f"GenieKey {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Opsgenie API error: {e}")

        self.logger.info("Opsgenie alert created")
        return {"status": "success"}
