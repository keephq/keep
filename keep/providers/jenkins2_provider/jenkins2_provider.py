"""Jenkins CI/CD provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class Jenkins2ProviderAuthConfig:
    url: str = dataclasses.field(
        metadata={"required": True, "description": "Jenkins URL"},
        default=""
    )
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Username"},
        default=""
    )
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "API Token", "sensitive": True},
        default=""
    )

class Jenkins2Provider(BaseProvider):
    """Jenkins CI/CD provider."""
    
    PROVIDER_DISPLAY_NAME = "Jenkins"
    PROVIDER_CATEGORY = ["CI/CD"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = Jenkins2ProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, job_name: str = "", **kwargs: Dict[str, Any]):
        if not job_name:
            raise ProviderException("Job name is required")

        try:
            response = requests.post(
                f"{self.authentication_config.url}/job/{job_name}/build",
                auth=(self.authentication_config.username, self.authentication_config.api_token),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Jenkins API error: {e}")

        self.logger.info("Jenkins build triggered")
        return {"status": "success"}
