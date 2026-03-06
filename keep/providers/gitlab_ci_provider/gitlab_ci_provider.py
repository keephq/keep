"""GitLab CI/CD provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GitLabCIProviderAuthConfig:
    host: str = dataclasses.field(
        metadata={"required": True, "description": "GitLab Host URL"},
        default="https://gitlab.com"
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Access Token", "sensitive": True},
        default=""
    )
    project_id: str = dataclasses.field(
        metadata={"required": True, "description": "Project ID"},
        default=""
    )

class GitLabCIProvider(BaseProvider):
    """GitLab CI/CD provider."""
    
    PROVIDER_DISPLAY_NAME = "GitLab CI"
    PROVIDER_CATEGORY = ["CI/CD"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GitLabCIProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, ref: str = "main", **kwargs: Dict[str, Any]):
        payload = {"ref": ref}

        try:
            response = requests.post(
                f"{self.authentication_config.host}/api/v4/projects/{self.authentication_config.project_id}/pipeline",
                json=payload,
                headers={"PRIVATE-TOKEN": self.authentication_config.access_token},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"GitLab CI API error: {e}")

        self.logger.info("GitLab CI pipeline triggered")
        return {"status": "success"}
