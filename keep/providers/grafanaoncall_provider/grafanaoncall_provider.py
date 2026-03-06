"""Grafana OnCall incident provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GrafanaOnCallProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Grafana OnCall API Key", "sensitive": True},
        default=""
    )

class GrafanaOnCallProvider(BaseProvider):
    """Grafana OnCall incident management provider."""
    
    PROVIDER_DISPLAY_NAME = "Grafana OnCall"
    PROVIDER_CATEGORY = ["Incident Management"]
    GRAFANA_API = "https://oncall-api.grafana.net/oncall"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GrafanaOnCallProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, title: str = "", message: str = "", **kwargs: Dict[str, Any]):
        if not title:
            raise ProviderException("Title is required")

        payload = {
            "title": title,
            "message": message
        }

        try:
            response = requests.post(
                f"{self.GRAFANA_API}/api/v1/alertgroups",
                json=payload,
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Grafana OnCall API error: {e}")

        self.logger.info("Grafana OnCall alert created")
        return {"status": "success"}
