"""Greenhouse ATS provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GreenhouseProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Greenhouse API Key", "sensitive": True},
        default=""
    )

class GreenhouseProvider(BaseProvider):
    """Greenhouse ATS provider."""
    
    PROVIDER_DISPLAY_NAME = "Greenhouse"
    PROVIDER_CATEGORY = ["Human Resources"]
    GREENHOUSE_API = "https://api.greenhouse.io/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GreenhouseProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, candidate_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not candidate_id:
            raise ProviderException("Candidate ID is required")

        try:
            response = requests.get(
                f"{self.GREENHOUSE_API}/candidates/{candidate_id}",
                headers={
                    "Authorization": f"Basic {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Greenhouse API error: {e}")

        self.logger.info(f"Greenhouse candidate data retrieved: {candidate_id}")
        return {"status": "success", "candidate_id": candidate_id}
