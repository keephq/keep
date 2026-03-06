"""Sketch design tool provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SketchProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Sketch API Key", "sensitive": True},
        default=""
    )

class SketchProvider(BaseProvider):
    """Sketch design tool provider."""
    
    PROVIDER_DISPLAY_NAME = "Sketch"
    PROVIDER_CATEGORY = ["Design & Creative"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SketchProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, document_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not document_id:
            raise ProviderException("Document ID is required")

        self.logger.info(f"Sketch document processed: {document_id}")
        return {"status": "success", "document_id": document_id}
