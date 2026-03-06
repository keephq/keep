"""CircleCI CI/CD provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class CircleCIProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "CircleCI API Token", "sensitive": True},
        default=""
    )

class CircleCIProvider(BaseProvider):
    """CircleCI CI/CD provider."""
    
    PROVIDER_DISPLAY_NAME = "CircleCI"
    PROVIDER_CATEGORY = ["CI/CD"]
    CIRCLECI_API = "https://circleci.com/api/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CircleCIProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, project_slug: str = "", branch: str = "main", **kwargs: Dict[str, Any]):
        if not project_slug:
            raise ProviderException("Project slug is required")

        payload = {"branch": branch}

        try:
            response = requests.post(
                f"{self.CIRCLECI_API}/project/{project_slug}/pipeline",
                json=payload,
                headers={"Circle-Token": self.authentication_config.api_token},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"CircleCI API error: {e}")

        self.logger.info("CircleCI pipeline triggered")
        return {"status": "success"}
