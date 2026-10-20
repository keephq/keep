import dataclasses
import http
import os
import time
from email.utils import parsedate_to_datetime

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class GoogleChatProviderAuthConfig:
    """Google Chat authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "name": "webhook_url",
            "description": "Google Chat Webhook Url",
            "required": True,
            "sensitive": True,
            "validation": "https_url",
        },
    )


class GoogleChatProvider(BaseProvider):
    """Send alert message to Google Chat."""

    PROVIDER_DISPLAY_NAME = "Google Chat"
    PROVIDER_TAGS = ["messaging"]
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GoogleChatProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, message="", **kwargs: dict):
        """
        Notify a message to a Google Chat room using a webhook URL.

        Args:
            message (str): The text message to send.

        Raises:
            ProviderException: If the message could not be sent successfully.
        """
        self.logger.debug("Notifying message to Google Chat")
        webhook_url = self.authentication_config.webhook_url

        if not message:
            raise ProviderException("Message is required")

        payload = {"text": message}
        headers = {"Content-Type": "application/json; charset=UTF-8"}
        retries = 3
        for attempt in range(retries):
            response = None
            try:
                response = requests.post(
                    webhook_url, json=payload, headers=headers, timeout=(5, 15)
                )
            except requests.exceptions.RequestException as error:
                # Request exception messages can contain the secret webhook URL.
                self.logger.warning(
                    "Google Chat attempt %s failed with %s",
                    attempt + 1,
                    type(error).__name__,
                )
            else:
                if response.status_code == http.HTTPStatus.OK:
                    self.logger.debug("Alert message sent to Google Chat successfully")
                    return "Alert message sent to Google Chat successfully"
                if response.status_code not in (408, 429) and not (
                    500 <= response.status_code < 600
                ):
                    raise ProviderException(
                        f"Google Chat rejected the message with status {response.status_code}"
                    )
                self.logger.warning(
                    "Google Chat attempt %s failed with status %s",
                    attempt + 1,
                    response.status_code,
                )
            if attempt < retries - 1:
                time.sleep(self._retry_delay(response, attempt))

        raise ProviderException(
            f"Failed to notify Google Chat after {retries} attempts"
        )

    @staticmethod
    def _retry_delay(response, attempt):
        """Respect Retry-After without blocking a worker for an unbounded period."""
        delay = 2**attempt
        retry_after = (
            response.headers.get("Retry-After") if response is not None else None
        )
        if retry_after:
            try:
                delay = max(delay, int(retry_after))
            except (TypeError, ValueError):
                try:
                    delay = max(
                        delay,
                        parsedate_to_datetime(retry_after).timestamp() - time.time(),
                    )
                except (TypeError, ValueError, OverflowError):
                    pass
        if delay > 60:
            # Retrying sooner than the server requested would amplify rate limiting.
            raise ProviderException(
                "Google Chat Retry-After exceeds the 60 second limit"
            )
        return delay


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
        name="Google Chat",
        description="Google Chat Output Provider",
        authentication={"webhook_url": google_chat_webhook_url},
    )
    provider = GoogleChatProvider(
        context_manager, provider_id="google-chat", config=config
    )
    provider.notify(message="Simple alert showing context with name: John Doe")
