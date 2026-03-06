"""Travis CI CI/CD provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class TravisCIProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Travis CI API Token", "sensitive": True},
        default=""
    )

class TravisCIProvider(BaseProvider):
    """Travis CI CI/CD provider."""
    
    PROVIDER_DISPLAY_NAME = "Travis CI"
    PROVIDER_CATEGORY = ["CI/CD"]
    TRAVISCI_API = "https://api.travis-ci.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TravisCIProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, repo_slug: str = "", branch: str = "main", **kwargs: Dict[str, Any]):
        if not repo_slug:
            raise ProviderException("Repo slug is required")

        payload = {
            "request": {
                "branch": branch,
                "config": kwargs.get("config", {})
            }
        }

        try:
            response = requests.post(
                f"{self.TRAVISCI_API}/repo/{repo_slug}/requests",
                json=payload,
                headers={
                    "Travis-API-Version": "3",
                    "Authorization": f"token {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Travis CI API error: {e}")

        self.logger.info(f"Travis CI build triggered: {repo_slug}")
        return {"status": "success", "repo_slug": repo_slug}
