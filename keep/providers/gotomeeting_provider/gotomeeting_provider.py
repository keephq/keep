"""GoToMeeting video conferencing provider."""

import dataclasses
from typing import Dict, Any

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GoToMeetingProviderAuthConfig:
    access_token: str = dataclasses.field(
        metadata={"required": True, "description": "GoToMeeting Access Token", "sensitive": True},
        default=""
    )

class GoToMeetingProvider(BaseProvider):
    """GoToMeeting video conferencing provider."""
    
    PROVIDER_DISPLAY_NAME = "GoToMeeting"
    PROVIDER_CATEGORY = ["Video Conferencing"]
    GOTOMEETING_API = "https://api.getgo.com/G2M/rest"

    def __init__(self, context_manager: ContextManager, provider_id: str, config: ProviderConfig):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GoToMeetingProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(self, subject: str = "", starttime: str = "", endtime: str = "", **kwargs: Dict[str, Any]):
        if not subject:
            raise ProviderException("Subject is required")

        payload = {
            "subject": subject,
            "starttime": starttime,
            "endtime": endtime
        }

        try:
            response = requests.post(
                f"{self.GOTOMEETING_API}/meetings",
                json=payload,
                headers={
                    "Authorization": f"Bearer {self.authentication_config.access_token}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"GoToMeeting API error: {e}")

        self.logger.info(f"GoToMeeting created: {subject}")
        return {"status": "success", "subject": subject}
