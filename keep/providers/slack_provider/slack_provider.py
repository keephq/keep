"""
SlackOutput is a class that implements the BaseOutputProvider interface for Slack messages.
"""
import dataclasses
import os

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class SlackProviderAuthConfig:
    """Slack authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Slack Webhook Url",
            "sensitive": True,
        },
        default="",
    )
    access_token: str = dataclasses.field(
        metadata={
            "description": "For access token installation flow, use Keep UI",
            "required": False,
            "sensitive": True,
            "hidden": True,
        },
        default="",
    )


class SlackProvider(BaseProvider):
    """Send alert message to Slack."""

    OAUTH2_URL = os.environ.get("SLACK_OAUTH2_URL")
    SLACK_CLIENT_ID = os.environ.get("SLACK_CLIENT_ID")
    SLACK_CLIENT_SECRET = os.environ.get("SLACK_CLIENT_SECRET")
    SLACK_API = "https://slack.com/api"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = SlackProviderAuthConfig(
            **self.config.authentication
        )
        if (
            not self.authentication_config.webhook_url
            and not self.authentication_config.access_token
        ):
            raise Exception("Slack webhook url OR Slack access token is required")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    @staticmethod
    def oauth2_logic(**payload):
        """
        Logic for handling oauth2 callback.

        Args:
            payload (dict): The payload from the oauth2 callback.

        Returns:
            dict: The provider configuration.
        """
        code = payload.get("code")
        if not code:
            raise Exception("No code provided")
        exchange_request_payload = {
            **payload,
            "client_id": SlackProvider.SLACK_CLIENT_ID,
            "client_secret": SlackProvider.SLACK_CLIENT_SECRET,
        }
        response = requests.post(
            f"{SlackProvider.SLACK_API}/oauth.v2.access",
            data=exchange_request_payload,
        )
        response_json = response.json()
        if not response.ok or not response_json.get("ok"):
            raise Exception(
                response_json.get("error"),
            )
        return {"access_token": response_json.get("access_token")}

    def _notify(self, message="", blocks=[], channel="", **kwargs: dict):
        """
        Notify alert message to Slack using the Slack Incoming Webhook API
        https://api.slack.com/messaging/webhooks

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying alert message to Slack")
        if not message:
            message = blocks[0].get("text")
        if self.authentication_config.webhook_url:
            self.logger.debug("Notifying alert message to Slack using webhook url")
            response = requests.post(
                self.authentication_config.webhook_url,
                json={"text": message, "blocks": blocks},
            )
            if not response.ok:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify alert message to Slack: {response.text}"
                )
        elif self.authentication_config.access_token:
            self.logger.debug("Notifying alert message to Slack using access token")
            if not channel:
                raise ProviderException("Channel is required (E.g. C12345)")
            payload = {
                "channel": channel,
                "text": message,
                "blocks": blocks,
                "token": self.authentication_config.access_token,
            }
            response = requests.post(
                f"{SlackProvider.SLACK_API}/chat.postMessage", data=payload
            )
            response_json = response.json()
            if not response.ok or not response_json.get("ok"):
                raise ProviderException(
                    f"Failed to notify alert message to Slack: {response_json.get('error')}"
                )
        self.logger.debug("Alert message notified to Slack")


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

    slack_webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    # Initalize the provider and provider config
    config = ProviderConfig(
        id="slack-test",
        description="Slack Output Provider",
        authentication={"webhook_url": slack_webhook_url},
    )
    provider = SlackProvider(context_manager, provider_id="slack", config=config)
    provider.notify(message="Simple alert showing context with name: John Doe")
