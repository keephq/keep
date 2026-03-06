"""Retool internal tools provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RetoolProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Retool API Key", "sensitive": True},
        default=""
    )
    retool_domain: str = dataclasses.field(
        metadata={"required": True, "description": "Retool Domain"},
        default=""
    )

class RetoolProvider(BaseProvider):
    """Retool internal tools provider."""
    
    PROVIDER_DISPLAY_NAME = "Retool"
    PROVIDER_CATEGORY = ["Developer Tools"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)
        self.api_url = f"https://{self.authentication_config.retool_domain}/api/v1"

    def validate_config(self):
        self.authentication_config = RetoolProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, workflow_id: str = "", **kwargs: Dict[str, Any]):
        if not workflow_id:
            raise ProviderException("Workflow ID is required")

        payload = kwargs.get("payload", {})

        try:
            response = requests.post(
                f"{self.api_url}/workflows/{workflow_id}/start",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Retool API error: {e}")

        self.logger.info(f"Retool workflow started: {workflow_id}")
        return {"status": "success", "workflow_id": workflow_id}
