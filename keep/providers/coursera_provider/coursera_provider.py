"""Coursera online learning provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class CourseraProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Coursera API Key", "sensitive": True},
        default=""
    )

class CourseraProvider(BaseModel):
    """Coursera online learning provider."""
    
    PROVIDER_DISPLAY_NAME = "Coursera"
    PROVIDER_CATEGORY = ["Education"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CourseraProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, course_id: str = "", progress: str = "", **kwargs: Dict[str, Any]):
        if not course_id or not progress:
            raise ProviderException("Course ID and progress are required")

        self.logger.info(f"Coursera course progress updated: {course_id}")
        return {"status": "success", "course_id": course_id}
