"""Gusto payroll provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GustoProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Gusto Access Token", "sensitive": True},
        default=""
    )

class GustoProvider(BaseProvider):
    """Gusto payroll provider."""
    
    PROVIDER_DISPLAY_NAME = "Gusto"
    PROVIDER_CATEGORY = ["Human Resources"]
    GUSTO_API = "https://api.gusto.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GustoProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, company_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not company_id:
            raise ProviderException("Company ID is required")

        try:
            response = requests.get(
                f"{self.GUSTO_API}/v1/companies/{company_id}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Gusto API error: {e}")

        self.logger.info(f"Gusto company data retrieved: {company_id}")
        return {"status": "success", "company_id": company_id}
