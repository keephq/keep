"""
ZulipProvider implements the BaseOutputProvider interface for Zulip notifications.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ZulipProviderAuthConfig:
    """Zulip authentication configuration."""

    zulip_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip server URL (e.g. https://yourorg.zulipchat.com)",
        }
    )
    email: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Bot email address (from Zulip bot settings)",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip bot API key",
            "sensitive": True,
        }
    )
    stream: str = dataclasses.field(
        default="general",
        metadata={
            "required": False,
            "description": "Stream name to send messages to",
        },
    )
    topic: str = dataclasses.field(
        default="Keep Alerts",
        metadata={
            "required": False,
            "description": "Topic/thread name within the stream",
        },
    )


class ZulipProvider(BaseProvider):
    """Send alert notifications to Zulip streams via bot API."""

    PROVIDER_DISPLAY_NAME = "Zulip"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ZulipProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(self, message: str = "", topic: str = "", **kwargs: dict):
        """
        Send a notification to a Zulip stream.

        Args:
            message (str): The message content (supports Zulip markdown).
            topic (str): Override the default topic/thread.
        """
        self.logger.debug("Sending notification to Zulip")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message to send"
            )

        base_url = self.authentication_config.zulip_url.rstrip("/")
        url = f"{base_url}/api/v1/messages"

        data = {
            "type": "stream",
            "to": self.authentication_config.stream,
            "topic": topic or self.authentication_config.topic,
            "content": message,
        }

        response = requests.post(
            url,
            auth=(self.authentication_config.email, self.authentication_config.api_key),
            data=data,
        )

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: "
                f"HTTP {response.status_code} - {response.text}"
            )

        result = response.json()
        if result.get("result") != "success":
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: {result.get('msg', 'unknown error')}"
            )

        self.logger.debug("Zulip notification sent successfully")
