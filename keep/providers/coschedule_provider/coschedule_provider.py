"""CoSchedule social media scheduling provider."""
import dataclasses
from typing import Dict, Any
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig

@pydantic.dataclasses.dataclass
class CoScheduleProviderAuthConfig:
    api_key: str = dataclasses.field(
        metadata={"required": True, "description": "CoSchedule API Key", "sensitive": True},
        default=""
    )

class CoScheduleProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "CoSchedule"
    PROVIDER_CATEGORY = ["Marketing & Advertising"]
    COSCHEDULE_API = "https://api.coschedule.com"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = CoScheduleProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, profile_id: str = "", post_text: str = "", **kwargs: Dict[str, Any]):
        if not profile_id or not post_text:
            raise ProviderException("Profile ID and post text are required")

        try:
            response = requests.post(
                f"{self.COSCHEDULE_API}/profiles/{profile_id}/updates/create",
                json={"text": post_text},
                headers={"Authorization": f"Bearer {self.authentication_config.api_key}"},
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"CoSchedule API error: {e}")

        self.logger.info(f"CoSchedule post created for profile {profile_id}")
        return {"status": "success", "profile_id": profile_id}
