"""Heroku cloud platform provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class HerokuProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Heroku API Key", "sensitive": True},
        default=""
    )
    app_name: str = dataclasses.field(
        metadata={"required": True, "description": "Heroku App Name"},
        default=""
    )

class HerokuProvider(BaseProvider):
    """Heroku cloud platform provider."""
    
    PROVIDER_DISPLAY_NAME = "Heroku"
    PROVIDER_CATEGORY = ["Web Hosting"]
    HEROKU_API = "https://api.heroku.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = HerokuProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, **kwargs: Dict[str, Any]):
        try:
            response = requests.post(
                f"{self.HEROKU_API}/apps/{self.authentication_config.app_name}/dynos",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_key}",
                    "Accept": "application/vnd.heroku+json; version=3"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Heroku API error: {e}")

        self.logger.info(f"Heroku dyno restarted: {self.authentication_config.app_name}")
        return {"status": "success", "app_name": self.authentication_config.app_name}
