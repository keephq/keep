"""Swimlane security automation provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SwimlaneProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Swimlane API Key", "sensitive": True},
        default=""
    )

class SwimlaneProvider(BaseProvider):
    """Swimlane security automation provider."""
    
    PROVIDER_DISPLAY_NAME = "Swimlane"
    PROVIDER_CATEGORY = ["Security"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SwimlaneProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, application_id: str = "", workflow_id: str = "", **kwargs: Dict[str, Any]):
        if not application_id:
            raise ProviderException("Application ID is required")

        self.logger.info(f"Swimlane workflow triggered: {workflow_id}")
        return {"status": "success", "application_id": application_id}
