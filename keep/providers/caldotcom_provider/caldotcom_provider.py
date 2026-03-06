"""Cal.com scheduling provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class CalComProviderAuthConfig:
    api_key: str = dataclasses.field(metadata={"required": True, "description": "Cal.com API Key", "sensitive": True}, default="")

class CalComProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Cal.com"
    PROVIDER_CATEGORY = ["Scheduling"]
    CALCOM_API = "https://api.cal.com/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CalComProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, booking_id: str = "", **kwargs: Dict[str, Any]):
        if not booking_id:
            raise ProviderException("Booking ID is required")
        try:
            response = requests.get(
                f"{self.CALCOM_API}/bookings/{booking_id}",
                params={"apiKey": self.authentication_config.api_key},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Cal.com API error: {e}")
        self.logger.info(f"Cal.com booking retrieved: {booking_id}")
        return {"status": "success", "booking_id": booking_id}
