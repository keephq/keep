"""
DiscordProvider is a class that implements the BaseOutputProvider interface for Discord messages.
"""
import dataclasses
import pydantic
import requests

from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DiscordProviderAuthConfig:
    """Discord authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Discord Webhook Url"}
    )


class DiscordProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        self.authentication_config = DiscordProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def notify(self, **kwargs: dict):
        """
        Notify alert message to Discord using the Discord Incoming Webhook API
        https://discord.com/developers/docs/resources/webhook

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying alert message to Discord")
        webhook_url = self.authentication_config.webhook_url
        content = kwargs.pop("content", "")
        components = kwargs.pop("components", [])

        if not content and not components:
            raise ProviderException(
                f"{self.__class__.__name__} Keyword Arguments Missing : content or components atleast one of them needed to trigger message"
            )

        response = requests.post(
            webhook_url,
            json={"content": content, "components": components},
        )
        if response.status_code != 204:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Discord: {response.text}"
            )

        self.logger.debug("Alert message notified to Discord")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Discord Output Provider",
        authentication={"webhook_url": discord_webhook_url},
    )
    provider = DiscordProvider(provider_id="discord-test", config=config)

    provider.notify(
        content="Hey Discord By: {name}".format(name="Sakthi Ratnam"),
    )
