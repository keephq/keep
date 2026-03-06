"""PhishLabs phishing protection provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PhishLabsProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "PhishLabs API Key", "sensitive": True},
        default=""
    )

class PhishLabsProvider(BaseModel):
    """PhishLabs phishing protection provider."""
    
    PROVIDER_DISPLAY_NAME = "PhishLabs"
    PROVIDER_CATEGORY = ["Security"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PhishLabsProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, incident_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not incident_id:
            raise ProviderException("Incident ID is required")

        self.logger.info(f"PhishLabs incident {incident_id}: {action}")
        return {"status": "success", "incident_id": incident_id}
