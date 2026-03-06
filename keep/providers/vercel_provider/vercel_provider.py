"""Vercel hosting provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class VercelProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Vercel Access Token", "sensitive": True},
        default=""
    )

class VercelProvider(BaseProvider):
    """Vercel hosting provider."""
    
    PROVIDER_DISPLAY_NAME = "Vercel"
    PROVIDER_CATEGORY = ["Web Hosting"]
    VERCEL_API = "https://api.vercel.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = VercelProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, project_id: str = "", **kwargs: Dict[str, Any]):
        if not project_id:
            raise ProviderException("Project ID is required")

        try:
            response = requests.post(
                f"{self.VERCEL_API}/deployments",
                json={"projectId": project_id},
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Vercel API error: {e}")

        self.logger.info(f"Vercel deployment triggered: {project_id}")
        return {"status": "success", "project_id": project_id}
