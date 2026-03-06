"""BambooHR HR management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BambooHRProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "BambooHR API Key", "sensitive": True},
        default=""
    )
    subdomain: str = dataclasses.field(
        metadata={"required": True, "description": "BambooHR Subdomain"},
        default=""
    )

class BambooHRProvider(BaseProvider):
    """BambooHR HR management provider."""
    
    PROVIDER_DISPLAY_NAME = "BambooHR"
    PROVIDER_CATEGORY = ["Human Resources"]
    BAMBOOHR_API = "https://api.bamboohr.com/api/gateway.php"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BambooHRProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, employee_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not employee_id:
            raise ProviderException("Employee ID is required")

        try:
            response = requests.get(
                f"{self.BAMBOOHR_API}/{self.authentication_config.subdomain}/v1/employees/{employee_id}",
                headers={
                    "Authorization": f"Basic {self.authentication_config.api_key}",
                    "Accept": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"BambooHR API error: {e}")

        self.logger.info(f"BambooHR employee data retrieved: {employee_id}")
        return {"status": "success", "employee_id": employee_id}
