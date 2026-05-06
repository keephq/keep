"""
GotifyProvider implements the BaseOutputProvider interface for Gotify push notifications.
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
class GotifyProviderAuthConfig:
    server_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify server URL (e.g. https://gotify.example.com)",
        }
    )
    app_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify application token",
            "sensitive": True,
        }
    )


class GotifyProvider(BaseProvider):
    """Send push notifications via Gotify self-hosted server."""

    PROVIDER_DISPLAY_NAME = "Gotify"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GotifyProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(
        self,
        message: str = "",
        title: str = "Keep Alert",
        priority: int = 5,
        **kwargs: dict,
    ):
        """
        Send a push notification via the Gotify REST API.
        https://gotify.net/docs/pushmsg

        Args:
            message (str): Notification body.
            title (str): Notification title (default: "Keep Alert").
            priority (int): Notification priority 0-10 (default: 5).
        """
        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message"
            )

        base_url = self.authentication_config.server_url.rstrip("/")
        url = f"{base_url}/message"

        response = requests.post(
            url,
            json={"title": title, "message": message, "priority": priority},
            params={"token": self.authentication_config.app_token},
        )

        if response.status_code not in (200, 201):
            raise ProviderException(
                f"{self.__class__.__name__} failed: HTTP {response.status_code} - {response.text}"
            )

        self.logger.debug("Gotify notification sent")


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    config = ProviderConfig(
        description="Gotify Output Provider",
        authentication={
            "server_url": os.environ.get("GOTIFY_SERVER_URL"),
            "app_token": os.environ.get("GOTIFY_APP_TOKEN"),
        },
    )
    provider = GotifyProvider(
        context_manager, provider_id="gotify-test", config=config
    )
    provider.notify(message="Test alert from Keep", title="Keep Alert", priority=5)
