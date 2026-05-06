"""
BarkProvider implements the BaseOutputProvider interface for Bark iOS push notifications.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class BarkProviderAuthConfig:
    device_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Bark device key from the Bark app",
            "sensitive": True,
        }
    )
    server_url: str = dataclasses.field(
        default="https://api.day.app",
        metadata={
            "required": False,
            "description": "Bark server URL (default: https://api.day.app, or your self-hosted URL)",
        },
    )


class BarkProvider(BaseProvider):
    """Send iOS push notifications via Bark."""

    PROVIDER_DISPLAY_NAME = "Bark"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = BarkProviderAuthConfig(**self.config.authentication)

    def dispose(self):
        pass

    def _notify(
        self,
        message: str = "",
        title: str = "Keep Alert",
        level: str = "active",
        **kwargs: dict,
    ):
        """
        Send an iOS push notification via Bark.

        Args:
            message (str): The body of the notification.
            title (str): The notification title.
            level (str): Notification interruption level: active, timeSensitive, passive, or critical.
        """
        if not message:
            raise ProviderException(f"{self.__class__.__name__} requires a message")

        self.logger.debug("Sending Bark notification")

        base = self.authentication_config.server_url.rstrip("/")
        url = f"{base}/push"
        payload = {
            "device_key": self.authentication_config.device_key,
            "title": title,
            "body": message,
            "level": level,
        }

        response = requests.post(url, json=payload)

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed: HTTP {response.status_code} - {response.text}"
            )

        result = response.json()
        if result.get("code") != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed: {result.get('message', 'unknown error')}"
            )

        self.logger.debug("Bark notification sent")


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    bark_device_key = os.environ.get("BARK_DEVICE_KEY")
    bark_server_url = os.environ.get("BARK_SERVER_URL", "https://api.day.app")

    config = ProviderConfig(
        id="bark-test",
        description="Bark Output Provider",
        authentication={"device_key": bark_device_key, "server_url": bark_server_url},
    )
    provider = BarkProvider(context_manager, provider_id="bark", config=config)
    provider.notify(message="Test alert from Keep", title="Keep Alert")
