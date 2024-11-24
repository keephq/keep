"""
DiscordProvider is a class that implements the BaseOutputProvider interface for Discord messages.
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
class DiscordProviderAuthConfig:
    """Discord authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Discord Webhook Url",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class DiscordProvider(BaseProvider):
    """Send alert message to Discord."""

    PROVIDER_DISPLAY_NAME = "Discord"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DiscordProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, content: str = "", components: list = [], **kwargs: dict):
        """
        Notify alert message to Discord using the Discord Incoming Webhook API
        https://discord.com/developers/docs/resources/webhook

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying alert message to Discord")
        webhook_url = self.authentication_config.webhook_url

        if not content and not components:
            raise ProviderException(
                f"{self.__class__.__name__} Keyword Arguments Missing : content or components atleast one of them needed to trigger message"
            )
        # verify components is a list
        if components and not isinstance(components, list):
            # omit it
            self.logger.warning(
                f"{self.__class__.__name__} components should be a list of components, omitting components"
            )
            components = []

        # send the request
        response = requests.post(
            webhook_url,
            json={"content": content, "components": components},
        )

        if response.status_code != 204:
            try:
                r = response.json()
            # unknown response
            except Exception:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to Discord: {response.text}"
                )

            # there can be plenty of errors, will be added over time
            if "components" in r and "ListType" in r["components"][0]:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to Discord: components should be a list of components"
                )
            # TODO: Add more error handling
            else:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to Discord: {response.text}"
                )

        self.logger.debug("Alert message notified to Discord")


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

    discord_webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="Discord Output Provider",
        authentication={"webhook_url": discord_webhook_url},
    )
    provider = DiscordProvider(
        context_manager, provider_id="discord-test", config=config
    )

    button_component = {
        "type": 1,
        "components": [
            {"type": 2, "style": 1, "label": "Click Me!", "custom_id": "button_click"}
        ],
    }

    provider.notify(
        content="Hey Discord By: Sakthi Ratnam", components=[button_component]
    )
