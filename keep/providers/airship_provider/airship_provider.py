"""Airship push notification provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class AirshipProviderAuthConfig:
    app_key: str = dataclasses.field(
        metadata={"required": True, "description": "Airship App Key"},
        default=""
    )
    master_secret: str = dataclasses.field(
        metadata={"required": True, "description": "Airship Master Secret", "sensitive": True},
        default=""
    )

class AirshipProvider(BaseProvider):
    """Airship push notification provider."""
    
    PROVIDER_DISPLAY_NAME = "Airship"
    PROVIDER_CATEGORY = ["Notifications"]
    AIRSHIP_API = "https://go.urbanairship.com/api"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AirshipProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, alert: str = "", **kwargs: Dict[str, Any]):
        if not alert:
            raise ProviderException("Alert is required")

        payload = {
            "audience": "all",
            "notification": {"alert": alert}
        }

        try:
            response = requests.post(
                f"{self.AIRSHIP_API}/push",
                json=payload,
                auth=(self.authentication_config.app_key, self.authentication_config.master_secret),
                headers={"Content-Type": "application/json"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Airship API error: {e}")

        self.logger.info("Airship notification sent")
        return {"status": "success"}
