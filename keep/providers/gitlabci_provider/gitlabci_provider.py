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
    private_token: str = dataclasses.field(
        metadata={"required": True, "description": "GitLab Private Token", "sensitive": True},
        default=""
    )
    gitlab_url: str = dataclasses.field(
        metadata={"required": True, "description": "GitLab URL"},
        default="https://gitlab.com"
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

    def _notify(self, project_id: str = "", ref: str = "main", **kwargs: Dict[str, Any]):
        if not project_id:
            raise ProviderException("Project ID is required")

        payload = {
            "ref": ref,
            "variables": kwargs.get("variables", [])
        }

        try:
            response = requests.post(
                f"{self.authentication_config.gitlab_url}/api/v4/projects/{project_id}/pipeline",
                json=payload,
                headers={
                    "PRIVATE-TOKEN": self.authentication_config.private_token,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"GitLab CI API error: {e}")

        self.logger.info(f"GitLab CI pipeline triggered: {project_id}")
        return {"status": "success", "project_id": project_id}
