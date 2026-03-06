"""Doodle scheduling provider."""
import dataclasses
from typing import Dict, Any
import pydantic
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class DoodleProviderAuthConfig:
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Doodle API Key", "sensitive": True}, default="")

class DoodleProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Doodle"
    PROVIDER_CATEGORY = ["Scheduling"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DoodleProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, poll_id: str = "", **kwargs: Dict[str, Any]):
        if not poll_id:
            raise ProviderException("Poll ID is required")
        self.logger.info(f"Doodle poll accessed: {poll_id}")
        return {"status": "success", "poll_id": poll_id}
