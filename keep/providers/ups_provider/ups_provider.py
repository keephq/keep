"""UPS shipping provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class UPSProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "UPS Access Token", "sensitive": True},
        default=""
    )

    account_number: str = dataclasses.field(
        metadata={"required": True, "description": "UPS Account Number"},
        default=""
    )

class UPSProvider(BaseProvider):
    """UPS shipping provider."""
    
    PROVIDER_DISPLAY_NAME = "UPS"
    PROVIDER_CATEGORY = ["Shipping & Logistics"]
    UPS_API = "https://onlinetools.ups.com/rest"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = UPSProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, tracking_number: str = "", **kwargs: Dict[str, Any]):
        if not tracking_number:
            raise ProviderException("Tracking number is required")

        payload = {
            "TrackingNumber": tracking_number,
            "Shipper": kwargs.get("shipper", {}).get("shipper", {}),
            "ServiceCode": kwargs.get("service_code", "03"),
            "Weight": "1",
            "Description": kwargs.get("description", ""),
            "Reference": kwargs.get("reference", {})
        }

        try:
            response = requests.post(
                f"{self.UPs_API}/shipments",
                json=payload,
                headers={
                    "AccessLicenseNumber": self.authentication_config.access_token,
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"UPS API error: {e}")

        self.logger.info(f"UPS shipment created: {tracking_number}")
        return {"status": "success", "tracking_number": tracking_number}
