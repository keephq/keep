"""OneSignal push notification provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class OneSignalProviderAuthConfig:
    app_id: str = dataclasses.field(
        metadata={"required": True, "description": "OneSignal App ID"},
        default=""
    )
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "OneSignal API Key", "sensitive": True},
        default=""
    )

class OneSignalProvider(BaseProvider):
    """OneSignal push notification provider."""
    
    PROVIDER_DISPLAY_NAME = "OneSignal"
    PROVIDER_CATEGORY = ["Notifications"]
    ONESIGNAL_API = "https://onesignal.com/api/v1"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = OneSignalProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, contents: str = "", headings: str = "", **kwargs: Dict[str, Any]):
        if not contents:
            raise ProviderException("Contents are required")

        payload = {
            "app_id": self.authentication_config.app_id,
            "contents": {"en": contents},
            "headings": {"en": headings} if headings else None,
            "included_segments": ["All"]
        }

        try:
            response = requests.post(
                f"{self.ONESIGNAL_API}/notifications",
                json=payload,
                headers={
                    "Authorization": f"Basic {self.authentication_config.api_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"OneSignal API error: {e}")

        self.logger.info("OneSignal notification sent")
        return {"status": "success", "id": response.json().get("id")}
