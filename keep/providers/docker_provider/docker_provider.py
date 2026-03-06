"""Docker Hub provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DockerProviderAuthConfig:
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Docker Hub Username"},
        default=""
    )
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Access Token", "sensitive": True},
        default=""
    )

class DockerProvider(BaseProvider):
    """Docker Hub provider."""
    
    PROVIDER_DISPLAY_NAME = "Docker Hub"
    PROVIDER_CATEGORY = ["Cloud"]
    DOCKER_API = "https://hub.docker.com/v2"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DockerProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, repository: str = "", description: str = "", **kwargs: Dict[str, Any]):
        if not repository:
            raise ProviderException("Repository is required")

        payload = {"description": description}

        try:
            response = requests.patch(
                f"{self.DOCKER_API}/repositories/{self.authentication_config.username}/{repository}/",
                json=payload,
                headers={"Authorization": f"JWT {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Docker Hub API error: {e}")

        self.logger.info("Docker Hub repository updated")
        return {"status": "success"}
