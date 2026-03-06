"""Canva design platform provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class CanvaProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Canva Access Token", "sensitive": True},
        default=""
    )

class CanvaProvider(BaseProvider):
    """Canva design platform provider."""
    
    PROVIDER_DISPLAY_NAME = "Canva"
    PROVIDER_CATEGORY = ["Design & Creative"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CanvaProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, design_id: str = "", title: str = "", **kwargs: Dict[str, Any]):
        if not design_id:
            raise ProviderException("Design ID is required")

        self.logger.info(f"Canva design processed: {design_id}")
        return {"status": "success", "design_id": design_id}
