"""
RocketChatProvider implements the BaseOutputProvider interface for Rocket.Chat notifications.
"""

import dataclasses
from typing import Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class RocketChatProviderAuthConfig:
    """Rocket.Chat authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat Incoming Webhook URL",
            "sensitive": True,
            "validation": "https_url",
        }
    )
    channel: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Override the default channel (e.g. #alerts). Leave empty to use webhook default.",
        },
    )
    username: str = dataclasses.field(
        default="Keep",
        metadata={
            "required": False,
            "description": "Bot display name in Rocket.Chat",
        },
    )


class RocketChatProvider(BaseProvider):
    """Send alert notifications to Rocket.Chat via incoming webhook."""

    PROVIDER_DISPLAY_NAME = "Rocket.Chat"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RocketChatProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(self, message: str = "", color: str = "#e74c3c", **kwargs: dict):
        """
        Send a notification to Rocket.Chat via incoming webhook.

        Args:
            message (str): The message content.
            color (str): Attachment color hex code. Defaults to red for alerts.
        """
        self.logger.debug("Sending notification to Rocket.Chat")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message to send"
            )

        payload: dict = {
            "text": message,
            "username": self.authentication_config.username,
            "icon_emoji": ":bell:",
        }

        if self.authentication_config.channel:
            payload["channel"] = self.authentication_config.channel

        response = requests.post(
            str(self.authentication_config.webhook_url), json=payload
        )

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: "
                f"HTTP {response.status_code} - {response.text}"
            )

        self.logger.debug("Rocket.Chat notification sent successfully")
