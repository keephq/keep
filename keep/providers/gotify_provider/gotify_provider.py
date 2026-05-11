"""
Gotify Provider is a class that implements the BaseOutputProvider interface for Gotify self-hosted push notifications.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GotifyProviderAuthConfig:
    """Gotify authentication configuration."""

    gotify_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify server URL (e.g. https://gotify.example.com)",
            "config_main_group": "authentication",
        }
    )

    app_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify application token",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )


class GotifyProvider(BaseProvider):
    """Send alert message to Gotify self-hosted push notification server."""

    PROVIDER_DISPLAY_NAME = "Gotify"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GotifyProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def validate_scopes(self):
        """
        Validate that the app token is valid by making a test request.
        """
        try:
            self._send_message("Keep test message", priority=0)
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(
        self,
        message: str,
        title: str = "Keep Alert",
        priority: int = 5,
    ):
        """
        Send a message to Gotify.
        https://gotify.net/docs/pushmsg
        """
        gotify_url = self.authentication_config.gotify_url.rstrip("/")
        app_token = self.authentication_config.app_token

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        headers = {
            "X-Gotify-Key": app_token,
            "Content-Type": "application/json",
        }

        payload = {
            "title": title,
            "message": message,
            "priority": priority,
        }

        response = requests.post(
            f"{gotify_url}/message",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code in [200, 201]:
            return response.json()
        elif response.status_code == 401:
            raise ProviderException(
                f"{self.__class__.__name__} unauthorized - invalid app token"
            )
        else:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: {response.status_code} - {response.text}"
            )

    def _notify(
        self,
        message: str = "",
        title: str = "Keep Alert",
        priority: int = 5,
        **kwargs: dict,
    ):
        """
        Notify alert message to Gotify.

        Args:
            message (str): The message body.
            title (str): The notification title.
            priority (int): Priority level (0=low, 5=normal, 10=high).
        """
        self.logger.debug("Notifying alert message to Gotify")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(
            message=message,
            title=title,
            priority=priority,
        )

        self.logger.debug("Alert message notified to Gotify")
        return {"message": message, "title": title, "priority": priority, "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    gotify_url = os.environ.get("GOTIFY_URL")
    app_token = os.environ.get("GOTIFY_TOKEN")

    if not gotify_url or not app_token:
        raise Exception("GOTIFY_URL and GOTIFY_TOKEN are required")

    config = ProviderConfig(
        description="Gotify Output Provider",
        authentication={"gotify_url": gotify_url, "app_token": app_token},
    )
    provider = GotifyProvider(
        context_manager, provider_id="gotify-test", config=config
    )

    provider.notify(message="Hello from Keep!", title="Test Alert")
