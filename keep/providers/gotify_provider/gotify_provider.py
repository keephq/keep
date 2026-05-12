"""
GotifyProvider is a class that implements the BaseOutputProvider interface for Gotify push notifications.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class GotifyProviderAuthConfig:
    """Gotify authentication configuration."""

    gotify_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify Server URL (e.g. https://push.example.com)",
            "sensitive": False,
            "validation": "https_url",
        }
    )
    app_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify Application Token",
            "sensitive": True,
        }
    )


class GotifyProvider(BaseProvider):
    """Send alert message to Gotify."""

    PROVIDER_DISPLAY_NAME = "Gotify"
    PROVIDER_CATEGORY = ["Messaging"]

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

    def _notify(self, content: str = "", title: str = "Keep Alert", priority: int = 5, **kwargs: dict):
        """
        Notify alert message to Gotify using the Gotify Message API
        https://gotify.net/docs/pushmsg

        Args:
            content (str): The content of the message.
            title (str, optional): The title of the message. Defaults to "Keep Alert".
            priority (int, optional): The priority of the message. Defaults to 5.
        """
        self.logger.debug("Notifying alert message to Gotify")
        gotify_url = self.authentication_config.gotify_url.rstrip("/")
        app_token = self.authentication_config.app_token

        if not content:
            raise ProviderException(
                f"{self.__class__.__name__} Keyword Arguments Missing : content is needed to trigger message"
            )

        message_endpoint = f"{gotify_url}/message"
        headers = {"X-Gotify-Key": app_token}
        
        payload = {
            "message": content,
            "title": title,
            "priority": priority,
        }

        # Send the request
        try:
            response = requests.post(
                message_endpoint,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if hasattr(e, "response") and e.response is not None:
                error_message += f" - {e.response.text}"
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Gotify: {error_message}"
            )

        self.logger.debug("Alert message notified to Gotify")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    gotify_url = os.environ.get("GOTIFY_URL")
    gotify_token = os.environ.get("GOTIFY_APP_TOKEN")

    if not gotify_url or not gotify_token:
        print("Please set GOTIFY_URL and GOTIFY_APP_TOKEN environment variables")
    else:
        # Initialize the provider and provider config
        config = ProviderConfig(
            description="Gotify Output Provider",
            authentication={"gotify_url": gotify_url, "app_token": gotify_token},
        )
        provider = GotifyProvider(
            context_manager, provider_id="gotify-test", config=config
        )

        provider.notify(content="Hey Gotify from Keep!", title="Test Alert", priority=8)
