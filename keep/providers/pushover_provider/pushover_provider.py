import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PushoverProviderAuthConfig:
    """Pushover authentication configuration."""

    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Pushover app token",
            "sensitive": True,
        }
    )
    user_key: str = dataclasses.field(
        metadata={"required": True, "description": "Pushover user key"}
    )


class PushoverProvider(BaseProvider):
    """Send alert message to Pushover."""

    PROVIDER_DISPLAY_NAME = "Pushover"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = PushoverProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, message=None, **kwargs: dict):
        """
        Notify alert message to Pushover using the Pushover API
        https://support.pushover.net/i44-example-code-and-pushover-libraries#python

        Args:
            kwargs (dict): The providers with context
        """
        self.logger.debug("Notifying alert message to Pushover")
        resp = requests.post(
            "https://api.pushover.net/1/messages.json",
            data={
                "token": self.authentication_config.token,
                "user": self.authentication_config.user_key,
                "message": message,
            },
        )
        resp.raise_for_status()
        self.logger.debug("Alert message notified to Pushover")


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

    pushover_token = os.environ.get("PUSHOVER_TOKEN")
    pushover_user_key = os.environ.get("PUSHOVER_USER_KEY")

    # Initalize the provider and provider config
    config = ProviderConfig(
        id="pushover-test",
        description="Pushover Output Provider",
        authentication={"token": pushover_token, "user_key": pushover_user_key},
    )
    provider = PushoverProvider(context_manager, provider_id="pushover", config=config)
    provider.notify(message="Simple alert showing context with name: John Doe")
