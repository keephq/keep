"""Microsoft Teams video conferencing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MSTeamsProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "Microsoft Teams Access Token", "sensitive": True},
        default=""
    )

class MSTeamsProvider(BaseProvider):
    """Microsoft Teams video conferencing provider."""
    
    PROVIDER_DISPLAY_NAME = "Microsoft Teams"
    PROVIDER_CATEGORY = ["Video Conferencing"]
    MSTEAMS_API = "https://graph.microsoft.com/v1.0"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MSTeamsProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, meeting_id: str = "", subject: str = "", **kwargs: Dict[str, Any]):
        if not meeting_id:
            raise ProviderException("Meeting ID is required")

        try:
            response = requests.get(
                f"{self.MSTEAMS_API}/me/onlineMeetings/{meeting_id}",
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Microsoft Teams API error: {e}")

        self.logger.info(f"Microsoft Teams meeting retrieved: {meeting_id}")
        return {"status": "success", "meeting_id": meeting_id}
