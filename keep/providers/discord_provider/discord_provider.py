"""
Discord provider is an interface for Discord messages via webhook.
"""

import dataclasses
from typing import Any, Dict, Optional, Union

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DiscordProviderAuthConfig:
    """Discord authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Discord Webhook URL",
            "sensitive": True,
        },
        default="",
    )


class DiscordProvider(BaseProvider):
    """Send alert messages to Discord via webhook."""

    PROVIDER_DISPLAY_NAME = "Discord"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validate provider configuration."""
        self.authentication_config = DiscordProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise Exception("Discord webhook URL is required")

    def dispose(self):
        """No cleanup needed."""
        pass

    def _notify(
        self,
        message: str = "",
        embeds: list = None,
        username: str = "",
        avatar_url: str = "",
        **kwargs: Dict[str, Any],
    ):
        """
        Send message to Discord via webhook.

        Args:
            message: The message content (can include Markdown)
            embeds: List of Discord embed objects
            username: Override webhook username
            avatar_url: Override webhook avatar URL
        """
        if not message and not embeds:
            raise ProviderException("Message or embeds required")

        payload = {}

        if message:
            payload["content"] = message
        if embeds:
            payload["embeds"] = embeds
        if username:
            payload["username"] = username
        if avatar_url:
            payload["avatar_url"] = avatar_url

        self.logger.debug(
            "Sending Discord notification",
            extra={"provider_id": self.provider_id}
        )

        try:
            response = requests.post(
                self.authentication_config.webhook_url,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Discord webhook failed: {e}")

        self.logger.info("Discord notification sent successfully")

        return {
            "status_code": response.status_code,
            "success": True
        }


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG)

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL", "")

    config = ProviderConfig(
        id="discord-test",
        description="Discord Provider Test",
        authentication={"webhook_url": webhook_url}
    )

    provider = DiscordProvider(context_manager, provider_id="discord", config=config)
    result = provider.notify(message="**Test notification from Keep!** 🚀")
    print(f"Result: {result}")
