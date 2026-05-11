"""
Flock Provider is a class that implements the BaseOutputProvider interface for Flock messages.
"""

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

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Flock incoming webhook URL",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )


class FlockProvider(BaseProvider):
    """Send alert message to Flock via incoming webhook."""

    PROVIDER_DISPLAY_NAME = "Flock"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FlockProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def validate_scopes(self):
        """
        Validate that the webhook URL works by sending a test message.
        """
        try:
            self._send_message("Keep test message")
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(self, message: str):
        """
        Send a message to Flock via incoming webhook.
        https://support.flock.com/hc/en-us/articles/360006943354-Incoming-webhooks
        """
        webhook_url = self.authentication_config.webhook_url

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        payload = {"text": message}

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            return {"status": response.status_code, "sent": True}
        else:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: {response.status_code} - {response.text}"
            )

    def _notify(self, message: str = "", **kwargs: dict):
        """
        Notify alert message to Flock.

        Args:
            message (str): The message to send.
        """
        self.logger.debug("Notifying alert message to Flock")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(message=message)

        self.logger.debug("Alert message notified to Flock")
        return {"message": message, "status": result.get("status"), "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    flock_webhook_url = os.environ.get("FLOCK_WEBHOOK_URL")

    if flock_webhook_url is None:
        raise Exception("FLOCK_WEBHOOK_URL is required")

    config = ProviderConfig(
        description="Flock Output Provider",
        authentication={"webhook_url": flock_webhook_url},
    )
    provider = FlockProvider(
        context_manager, provider_id="flock-test", config=config
    )

    provider.notify(message="Hello from Keep!")
