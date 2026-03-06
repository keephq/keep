"""Railway cloud platform provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RailwayProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Railway API Token", "sensitive": True},
        default=""
    )

class RailwayProvider(BaseProvider):
    """Railway cloud platform provider."""
    
    PROVIDER_DISPLAY_NAME = "Railway"
    PROVIDER_CATEGORY = ["Web Hosting"]
    RAILWAY_API = "https://backboard.railway.app/graphql/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RailwayProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, project_id: str = "", **kwargs: Dict[str, Any]):
        if not project_id:
            raise ProviderException("Project ID is required")

        try:
            response = requests.post(
                self.RAILWAY_API,
                json={"query": f"{{ project(id: \"{project_id}\") {{ name }} }}"},
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Railway API error: {e}")

        self.logger.info(f"Railway project accessed: {project_id}")
        return {"status": "success", "project_id": project_id}
