"""
SlackOutput is a class that implements the BaseOutputProvider interface for Slack messages.
"""
import dataclasses

import pydantic
import requests

from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SlackProviderAuthConfig:
    """Slack authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={"required": True, "description": "Slack Webhook Url"}
    )


class SlackProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def validate_config(self):
        self.authentication_config = SlackProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def notify(self, **kwargs: dict):
        """
        Notify alert message to Slack using the Slack Incoming Webhook API
        https://api.slack.com/messaging/webhooks

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying alert message to Slack")
        webhook_url = self.authentication_config.webhook_url
        message = kwargs.pop("message", "")
        blocks = kwargs.pop("blocks", [])

        if not message:
            message = blocks[0].get("text")
        response = requests.post(
            webhook_url,
            json={"text": message, "blocks": blocks},
        )
        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Slack: {response.text}"
            )

        self.logger.debug("Alert message notified to Slack")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    # Initalize the provider and provider config
    config = ProviderConfig(
        id="slack-test",
        description="Slack Output Provider",
        authentication={"webhook_url": slack_webhook_url},
    )
    provider = SlackProvider(config=config)
    provider.notify(message="Simple alert showing context with name: John Doe")
