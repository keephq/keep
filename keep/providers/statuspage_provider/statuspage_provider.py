"""Statuspage incident provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class StatuspageProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Statuspage API Key", "sensitive": True},
        default=""
    )
    page_id: str = dataclasses.field(
        metadata={"required": True, "description": "Statuspage Page ID"},
        default=""
    )

class StatuspageProvider(BaseProvider):
    """Statuspage incident management provider."""
    
    PROVIDER_DISPLAY_NAME = "Statuspage"
    PROVIDER_CATEGORY = ["Incident Management"]
    STATUSPAGE_API = "https://api.statuspage.io/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = StatuspageProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, name: str = "", status: str = "investigating", message: str = "", **kwargs: Dict[str, Any]):
        if not name:
            raise ProviderException("Incident name is required")

        payload = {
            "incident": {
                "name": name,
                "status": status,
                "body": message
            }
        }

        try:
            response = requests.post(
                f"{self.STATUSPAGE_API}/pages/{self.authentication_config.page_id}/incidents",
                json=payload,
                headers={"Authorization": f"OAuth {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Statuspage API error: {e}")

        self.logger.info("Statuspage incident created")
        return {"status": "success"}
