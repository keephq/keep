"""
RocketchatProvider is a class that implements the BaseOutputProvider interface for Rocket.Chat messages.
"""

import dataclasses

import json5
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RocketchatProviderAuthConfig:
    """Rocket.Chat authentication configuration."""

    webhook_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat Incoming Webhook Url",
            "sensitive": True,
            "validation": "any_http_url",
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

    def _notify(
        self,
        message="",
        attachments=[],
        channel="",
        alias="",
        emoji="",
        avatar="",
        **kwargs: dict,
    ):
        """
        Notify alert message to Rocket.Chat using the Rocket.Chat Incoming Webhook API
        https://developer.rocket.chat/docs/integrations

        Args:
            message (str): The content of the message.
            attachments (list): The attachments of the message.
            channel (str): The channel to send the message to, overriding the webhook default.
            alias (str): Display name to post the message under.
            emoji (str): Emoji to use as the avatar, e.g. ":ghost:".
            avatar (str): Image url to use as the avatar.
        """
        self.logger.info("Notifying alert message to Rocket.Chat")
        if not message:
            if not attachments:
                raise ProviderException(
                    f"{self.__class__.__name__} Keyword Arguments Missing : message or attachments at least one of them needed to trigger message"
                )
            message = attachments[0].get("text")
        webhook_url = self.authentication_config.webhook_url
        payload = {"text": message, **kwargs}

        if channel:
            payload["channel"] = channel
        if alias:
            payload["alias"] = alias
        if emoji:
            payload["emoji"] = emoji
        if avatar:
            payload["avatar"] = avatar

        if attachments:
            try:
                attachments = json5.loads(attachments)
            except Exception:
                pass
            payload["attachments"] = attachments

        response = requests.post(webhook_url, json=payload)

        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Rocket.Chat: {response.text}"
            )

        self.logger.info(
            "Alert message notified to Rocket.Chat", extra={"response": response.text}
        )


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

    # Initalize the provider and provider config
    config = ProviderConfig(
        id="rocketchat-test",
        description="Rocket.Chat Output Provider",
        authentication={"webhook_url": rocketchat_webhook_url},
    )
    provider = RocketchatProvider(
        context_manager, provider_id="rocketchat", config=config
    )
    provider.notify(message="Simple alert showing context with name: John Doe")
