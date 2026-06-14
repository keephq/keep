import dataclasses
import os

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

    def _notify(
        self,
        message: str = "",
        title: str | None = None,
        priority: int = 0,
        sound: str = "pushover",
        retry: int = 60,
        expire: int = 3600,
        **kwargs: dict,
    ):
        """
        Notify alert message to Pushover using the Pushover API
        https://support.pushover.net/i44-example-code-and-pushover-libraries#python

        Args:
            message (str): The content of the message.
            title (str | None): Optional notification title.
            priority (int): Message priority (-2 to 2, where 2 is emergency).
            sound (str): Pushover sound name.
            retry (int): Retry interval in seconds for emergency priority.
            expire (int): Expiry in seconds for emergency priority.
        """
        self.logger.debug("Notifying alert message to Pushover")
        sound = kwargs.get("sound", sound)
        priority = int(kwargs.get("priority", priority))
        retry = int(kwargs.get("retry", retry))
        expire = int(kwargs.get("expire", expire))
        title = kwargs.get("title", title)
        
        if isinstance(message, str):
            message = message.replace("<p>", "").replace("</p>", "")

        data = {
            "token": self.authentication_config.token,
            "user": self.authentication_config.user_key,
            "message": message,
            "sound": sound,
            "priority": priority,
            **({"retry": retry, "expire": expire} if priority == 2 else {}),
        }

        # Add optional title if provided so Pushover shows incident name as bold title
        if title:
            data["title"] = title

        resp = requests.post("https://api.pushover.net/1/messages.json", data=data)
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
