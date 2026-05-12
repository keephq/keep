"""
RocketchatProvider is a class that implements the BaseOutputProvider interface for Rocket.Chat messages.
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
class RocketchatProviderAuthConfig:
    """Rocket.Chat authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat Webhook Url",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class RocketchatProvider(BaseProvider):
    """Send alert message to Rocket.Chat."""

    PROVIDER_DISPLAY_NAME = "Rocket.Chat"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RocketchatProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, content: str = "", **kwargs: dict):
        """
        Notify alert message to Rocket.Chat using the Rocket.Chat Incoming Webhook API
        https://docs.rocket.chat/use-rocket.chat/workspace-administration/integrations

        Args:
            content (str): The content of the message.
        """
        self.logger.debug("Notifying alert message to Rocket.Chat")
        webhook_url = self.authentication_config.webhook_url

        if not content:
            raise ProviderException(
                f"{self.__class__.__name__} Keyword Arguments Missing : content is needed to trigger message"
            )

        # Rocket.Chat webhook body
        # Standard incoming webhook expect a "text" field
        payload = {"text": content}

        # Send the request
        response = requests.post(
            webhook_url,
            json=payload,
        )

        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Rocket.Chat: {response.text}"
            )

        self.logger.debug("Alert message notified to Rocket.Chat")


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

    rocketchat_webhook_url = os.environ.get("ROCKETCHAT_WEBHOOK_URL")

    if not rocketchat_webhook_url:
        print("Please set ROCKETCHAT_WEBHOOK_URL environment variable")
    else:
        # Initialize the provider and provider config
        config = ProviderConfig(
            description="Rocket.Chat Output Provider",
            authentication={"webhook_url": rocketchat_webhook_url},
        )
        provider = RocketchatProvider(
            context_manager, provider_id="rocketchat-test", config=config
        )

        provider.notify(content="Hey Rocket.Chat from Keep!")
