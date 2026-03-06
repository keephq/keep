"""Udemy online learning provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class UdemyProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Udemy Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Udemy Client Secret", "sensitive": True},
        default=""
    )

class UdemyProvider(BaseModel):
    """Udemy online learning provider."""
    
    PROVIDER_DISPLAY_NAME = "Udemy"
    PROVIDER_CATEGORY = ["Education"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = UdemyProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, course_id: str = "", lecture: str = "", **kwargs: Dict[str, Any]):
        if not course_id or not lecture:
            raise ProviderException("Course ID and lecture are required")

        self.logger.info(f"Udemy lecture completed: {course_id}")
        return {"status": "success", "course_id": course_id}
