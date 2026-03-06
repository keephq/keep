"""Acuity Scheduling provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class AcuityProviderAuthConfig:
    user_id: str = dataclasses.field(metadata={"required": True, "description": "Acuity User ID"}, default="")
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Acuity API Key", "sensitive": True}, default="")

class AcuityProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Acuity Scheduling"
    PROVIDER_CATEGORY = ["Scheduling"]
    ACUITY_API = "https://acuityscheduling.com/api/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AcuityProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, appointment_id: str = "", **kwargs: Dict[str, Any]):
        if not appointment_id:
            raise ProviderException("Appointment ID is required")
        try:
            response = requests.get(
                f"{self.ACUITY_API}/appointments/{appointment_id}",
                auth=(self.authentication_config.user_id, self.authentication_config.api_key),
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Acuity API error: {e}")
        self.logger.info(f"Acuity appointment retrieved: {appointment_id}")
        return {"status": "success", "appointment_id": appointment_id}
