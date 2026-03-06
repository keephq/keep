"""ServiceNow ITSM provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ServiceNowProviderAuthConfig:
    instance_url: str = dataclasses.field(
        metadata={"required": True, "description": "ServiceNow Instance URL"},
        default=""
    )
    username: str = dataclasses.field(
        metadata={"required": True, "description": "Username"},
        default=""
    )
    password: str = dataclasses.field(
        metadata={"required": True, "description": "Password", "sensitive": True},
        default=""
    )

class ServiceNowProvider(BaseProvider):
    """ServiceNow ITSM provider."""
    
    PROVIDER_DISPLAY_NAME = "ServiceNow"
    PROVIDER_CATEGORY = ["ITSM"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ServiceNowProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, short_description: str = "", description: str = "", priority: int = 3, **kwargs: Dict[str, Any]):
        if not short_description:
            raise ProviderException("Short description is required")

        payload = {
            "short_description": short_description,
            "description": description or short_description,
            "priority": str(priority)
        }

        try:
            response = requests.post(
                f"{self.authentication_config.instance_url}/api/now/table/incident",
                json=payload,
                auth=(self.authentication_config.username, self.authentication_config.password),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"ServiceNow API error: {e}")

        self.logger.info("ServiceNow incident created")
        return {"status": "success"}
