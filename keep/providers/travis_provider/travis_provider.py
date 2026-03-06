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
class TravisProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Travis CI API Token", "sensitive": True},
        default=""
    )
    repo: str = dataclasses.field(
        metadata={"required": True, "description": "Repository (owner/repo)"},
        default=""
    )

class TravisProvider(BaseProvider):
    """Travis CI CI/CD provider."""
    
    PROVIDER_DISPLAY_NAME = "Travis CI"
    PROVIDER_CATEGORY = ["CI/CD"]
    TRAVIS_API = "https://api.travis-ci.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = TravisProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, branch: str = "main", **kwargs: Dict[str, Any]):
        payload = {"request": {"branch": branch}}

        try:
            response = requests.post(
                f"{self.TRAVIS_API}/repo/{self.authentication_config.repo.replace('/', '%2F')}/requests",
                json=payload,
                headers={
                    "Travis-API-Version": "3",
                    "Authorization": f"token {self.authentication_config.api_token}"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Travis CI API error: {e}")

        self.logger.info("Travis CI build triggered")
        return {"status": "success"}
