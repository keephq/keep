"""Asana project management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AsanaProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Asana Access Token", "sensitive": True},
        default=""
    )

class AsanaProvider(BaseModel):
    """Asana project management provider."""
    
    PROVIDER_DISPLAY_NAME = "Asana"
    PROVIDER_CATEGORY = ["Collaboration"]
    ASANA_API = "https://app.asana.com/api/1.0"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AsanaProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, workspace: str = "", name: str = "", notes: str = "", **kwargs: Dict[str, Any]):
        if not name:
            raise ProviderException("Name is required")

        payload = {
            "data": {
                "workspace": workspace,
                "name": name,
                "notes": notes or name
            }
        }

        try:
            response = requests.post(
                f"{self.ASANA_API}/tasks",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.access_token}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Asana API error: {e}")

        self.logger.info("Asana task created")
        return {"status": "success"}
