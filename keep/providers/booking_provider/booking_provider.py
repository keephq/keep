"""Booking.com accommodation provider."""

import dataclasses
from typing import Dict, Any

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BookingProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "Booking.com API Key", "sensitive": True},
        default=""
    )

class BookingProvider(BaseModel):
    """Booking.com accommodation provider."""
    
    PROVIDER_DISPLAY_NAME = "Booking.com"
    PROVIDER_CATEGORY = ["Travel & Transportation"]

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BookingProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, hotel_id: str = "", check_in: str = "", check_out: str = "", **kwargs: Dict[str, Any]):
        if not hotel_id:
            raise ProviderException("Hotel ID is required")

        self.logger.info(f"Booking.com reservation for hotel {hotel_id}")
        return {"status": "success", "hotel_id": hotel_id}
