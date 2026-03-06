"""Sanity headless CMS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SanityProviderAuthConfig:
    api_token: str = dataclasses.field(
        metadata={"required": True, "description": "Sanity API Token", "sensitive": True},
        default=""
    )
    project_id: str = dataclasses.field(
        metadata={"required": True, "description": "Sanity Project ID"},
        default=""
    )

class SanityProvider(BaseProvider):
    """Sanity headless CMS provider."""
    
    PROVIDER_DISPLAY_NAME = "Sanity"
    PROVIDER_CATEGORY = ["Content Management"]
    SANITY_API = "https://api.sanity.io/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SanityProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, dataset: str = "", mutations: list = None, **kwargs: Dict[str, Any]):
        if not dataset or not mutations:
            raise ProviderException("Dataset and mutations are required")

        payload = {
            "mutations": mutations
        }

        try:
            response = requests.post(
                f"{self.SANITY_API}/data/mutate/{dataset}",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.api_token}",
                    "Content-Type": "application/json"
                },
                params={"projectId": self.authentication_config.project_id},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Sanity API error: {e}")

        self.logger.info(f"Sanity mutation applied: {dataset}")
        return {"status": "success", "dataset": dataset}
