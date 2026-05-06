"""
LineNotifyProvider implements the BaseOutputProvider interface for LINE Notify.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LineNotifyProviderAuthConfig:
    """LINE Notify authentication configuration."""

    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "LINE Notify access token from notify-bot.line.me",
            "sensitive": True,
        }
    )


class LineNotifyProvider(BaseProvider):
    """Send alert notifications via LINE Notify."""

    PROVIDER_DISPLAY_NAME = "LINE Notify"
    PROVIDER_CATEGORY = ["Collaboration"]
    LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LineNotifyProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(self, message: str = "", **kwargs: dict):
        """
        Send a notification via LINE Notify.

        Args:
            message (str): The message content (max 1000 characters).
        """
        self.logger.debug("Sending notification via LINE Notify")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message to send"
            )

        headers = {
            "Authorization": f"Bearer {self.authentication_config.token}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        response = requests.post(
            self.LINE_NOTIFY_URL,
            headers=headers,
            data={"message": message},
        )

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: "
                f"HTTP {response.status_code} - {response.text}"
            )

        result = response.json()
        if result.get("status") != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: {result.get('message', 'unknown error')}"
            )

        self.logger.debug("LINE Notify notification sent successfully")
