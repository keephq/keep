"""GitHub Actions CI/CD provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GitHubActionsProviderAuthConfig:
    token: str = dataclasses.field(
        metadata={"required": True, "description": "GitHub Token", "sensitive": True},
        default=""
    )
    owner: str = dataclasses.field(
        metadata={"required": True, "description": "Repository Owner"},
        default=""
    )
    repo: str = dataclasses.field(
        metadata={"required": True, "description": "Repository Name"},
        default=""
    )

class GitHubActionsProvider(BaseProvider):
    """GitHub Actions CI/CD provider."""
    
    PROVIDER_DISPLAY_NAME = "GitHub Actions"
    PROVIDER_CATEGORY = ["CI/CD"]
    GITHUB_API = "https://api.github.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GitHubActionsProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, workflow_id: str = "", ref: str = "main", **kwargs: Dict[str, Any]):
        if not workflow_id:
            raise ProviderException("Workflow ID is required")

        try:
            response = requests.post(
                f"{self.GITHUB_API}/repos/{self.authentication_config.owner}/{self.authentication_config.repo}/actions/workflows/{workflow_id}/dispatches",
                json={"ref": ref},
                headers={
                    "Authorization": f"token {self.authentication_config.token}",
                    "Accept": "application/vnd.github.v3+json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"GitHub Actions API error: {e}")

        self.logger.info("GitHub Actions workflow triggered")
        return {"status": "success"}
