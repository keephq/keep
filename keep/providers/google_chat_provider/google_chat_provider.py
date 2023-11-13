import os

import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


class GoogleChatProvider(BaseProvider):
    """Send alert message to Google Chat."""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        if not self.config.authentication.get("webhook_url"):
            raise Exception("Google Chat webhook URL is required")

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def notify(self, message="", **kwargs: dict):
        """
        Notify a message to a Google Chat room using a webhook URL.

        Args:
            message (str): The text message to send.

        Raises:
            ProviderException: If the message could not be sent successfully.
        """
        self.logger.debug("Notifying message to Google Chat")
        webhook_url = self.config.authentication.get("webhook_url")

        if not message:
            raise ProviderException("Message is required")

        payload = {
            "text": message,
        }

        requestHeaders = {"Content-Type": "application/json; charset=UTF-8"}

        response = requests.post(webhook_url, json=payload, headers=requestHeaders)

        if not response.ok:
            raise ProviderException(
                f"Failed to notify message to Google Chat: {response.text}"
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
    google_chat_webhook_url = os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")

    # Initialize the provider and provider config
    config = ProviderConfig(
        id="google-chat-test",
        description="Google Chat Output Provider",
        authentication={"webhook_url": google_chat_webhook_url},
    )
    provider = GoogleChatProvider(
        context_manager, provider_id="google-chat", config=config
    )
    provider.notify(message="Simple alert showing context with name: John Doe")
