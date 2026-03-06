"""Looker data analytics provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LookerProviderAuthConfig:
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Looker Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Looker Client Secret", "sensitive": True},
        default=""
    )
    base_url: str = dataclasses.field(
        metadata={"required": True, "description": "Looker Base URL"},
        default=""
    )

class LookerProvider(BaseProvider):
    """Looker data analytics provider."""
    
    PROVIDER_DISPLAY_NAME = "Looker"
    PROVIDER_CATEGORY = ["Data Analytics"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LookerProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, lookml_model: str = "", view: str = "", **kwargs: Dict[str, Any]):
        if not lookml_model or not view:
            raise ProviderException("LookML model and view are required")

        try:
            response = requests.post(
                f"{self.authentication_config.base_url}/api/4.0/lookml_models/{lookml_model}/views/{view}/refresh",
                headers={
                    "Authorization": f"token {self.authentication_config.client_secret}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Looker API error: {e}")

        self.logger.info(f"Looker view refreshed: {view}")
        return {"status": "success", "view": view}
