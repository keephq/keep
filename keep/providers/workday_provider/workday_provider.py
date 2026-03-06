"""Workday HR management provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WorkdayProviderAuthConfig:
    tenant_id: str = dataclasses.field(
        metadata={"required": True, "description": "Workday Tenant ID"},
        default=""
    )
    client_id: str = dataclasses.field(
        metadata={"required": True, "description": "Workday Client ID"},
        default=""
    )
    client_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Workday Client Secret", "sensitive": True},
        default=""
    )

class WorkdayProvider(BaseProvider):
    """Workday HR management provider."""
    
    PROVIDER_DISPLAY_NAME = "Workday"
    PROVIDER_CATEGORY = ["Human Resources"]
    WORKDAY_API = "https://api.workday.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WorkdayProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, employee_id: str = "", action: str = "", **kwargs: Dict[str, Any]):
        if not employee_id:
            raise ProviderException("Employee ID is required")

        try:
            response = requests.get(
                f"{self.WORKDAY_API}/v1/employees/{employee_id}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.client_id}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Workday API error: {e}")

        self.logger.info(f"Workday employee data retrieved: {employee_id}")
        return {"status": "success", "employee_id": employee_id}
