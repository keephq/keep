"""
WebexProvider implements the BaseOutputProvider interface for Cisco Webex notifications.
"""

import dataclasses
from typing import Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WebexProviderAuthConfig:
    """Cisco Webex authentication configuration."""

    bot_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Webex Bot Access Token from developer.webex.com",
            "sensitive": True,
        }
    )
    room_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Webex Room/Space ID where messages will be sent",
        }
    )


class WebexProvider(BaseProvider):
    """Send alert notifications to Cisco Webex rooms via bot."""

    PROVIDER_DISPLAY_NAME = "Webex"
    PROVIDER_CATEGORY = ["Collaboration"]
    WEBEX_API_URL = "https://webexapis.com/v1/messages"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WebexProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(self, message: str = "", use_markdown: bool = False, **kwargs: dict):
        """
        Send a notification to a Cisco Webex room.

        Args:
            message (str): The message content.
            use_markdown (bool): Send as markdown if True, plain text if False.
        """
        self.logger.debug("Sending notification to Webex")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message to send"
            )

        headers = {
            "Authorization": f"Bearer {self.authentication_config.bot_token}",
            "Content-Type": "application/json",
        }

        if use_markdown:
            payload = {
                "roomId": self.authentication_config.room_id,
                "markdown": message,
            }
        else:
            payload = {
                "roomId": self.authentication_config.room_id,
                "text": message,
            }

        response = requests.post(self.WEBEX_API_URL, headers=headers, json=payload)

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: "
                f"HTTP {response.status_code} - {response.text}"
            )

        self.logger.debug("Webex notification sent successfully")
