"""GitHub repository provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class GitHubRepoProviderAuthConfig:
    token: str = dataclasses.field(metadata={"required": True, "description": "GitHub Personal Access Token", "sensitive": True}, default="")

class GitHubRepoProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "GitHub Repo"
    PROVIDER_CATEGORY = ["Version Control"]
    GITHUB_API = "https://api.github.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GitHubRepoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, repo: str = "", branch: str = "", **kwargs: Dict[str, Any]):
        if not repo:
            raise ProviderException("Repo is required")
        try:
            response = requests.post(f"{self.GITHUB_API}/repos", json={"name": repo}, "private": False}, headers={"Authorization": f"token {self.authentication_config.token}"}, timeout=30)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"GitHub API error: {e}")
        self.logger.info(f"GitHub repo created: {repo}")
        return {"status": "success", "repo": repo}
