import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FlockProviderAuthConfig:
    """Flock authentication configuration."""

    webhook_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Flock Incoming Webhook URL (https://api.flock.com/hooks/sendMessage/...)",
            "sensitive": True,
            "validation": "any_http_url",
        }
    )


class FlockProvider(BaseProvider):
    """Send alert notifications to Flock channels via incoming webhook."""

    PROVIDER_DISPLAY_NAME = "Flock"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FlockProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(
        self,
        message: str = "",
        title: str = "",
        color: str = "#e74c3c",
        **kwargs: dict,
    ):
        """
        Send a notification to Flock via incoming webhook.
        https://dev.flock.com/webhooks

        Args:
            message (str): The message text to send.
            title (str): Optional title rendered as an attachment header.
            color (str): Hex color for the attachment sidebar (default red).
        """
        self.logger.info("Notifying alert message to Flock")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a non-empty message"
            )

        webhook_url = str(self.authentication_config.webhook_url)

        if title:
            payload = {
                "attachments": [
                    {"title": title, "description": message, "color": color}
                ]
            }
        else:
            payload = {"text": message}

        response = requests.post(webhook_url, json=payload)

        if not response.ok:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Flock: HTTP {response.status_code} - {response.text}"
            )

        self.logger.info(
            "Alert message notified to Flock", extra={"response": response.text}
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    flock_webhook_url = os.environ.get("FLOCK_WEBHOOK_URL")

    config = ProviderConfig(
        id="flock-test",
        description="Flock Output Provider",
        authentication={"webhook_url": flock_webhook_url},
    )
    provider = FlockProvider(context_manager, provider_id="flock", config=config)
    provider.notify(message="Simple alert showing context with name: John Doe")
