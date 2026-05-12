"""
ZulipProvider is a class that implements the BaseOutputProvider interface for Zulip messages.
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
class ZulipProviderAuthConfig:
    """Zulip authentication configuration."""

    zulip_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip Server URL (e.g. https://yourdomain.zulipchat.com)",
            "sensitive": False,
            "validation": "https_url",
        }
    )
    bot_email: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip Bot Email Address",
            "sensitive": False,
        }
    )
    bot_api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip Bot API Key",
            "sensitive": True,
        }
    )


class ZulipProvider(BaseProvider):
    """Send alert message to Zulip."""

    PROVIDER_DISPLAY_NAME = "Zulip"
    PROVIDER_CATEGORY = ["Collaboration", "Messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = ZulipProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(
        self,
        content: str = "",
        message_type: str = "stream",
        to: str = "general",
        topic: str = "Keep Alerts",
        **kwargs: dict,
    ):
        """
        Notify alert message to Zulip using the Zulip REST API
        https://zulip.com/api/send-message

        Args:
            content (str): The content of the message.
            message_type (str, optional): The type of message ("stream" or "private"). Defaults to "stream".
            to (str, optional): The name of the stream or the email of the user. Defaults to "general".
            topic (str, optional): The topic of the message (only for stream messages). Defaults to "Keep Alerts".
        """
        self.logger.debug("Notifying alert message to Zulip")
        zulip_url = self.authentication_config.zulip_url.rstrip("/")
        bot_email = self.authentication_config.bot_email
        bot_api_key = self.authentication_config.bot_api_key

        if not content:
            raise ProviderException(
                f"{self.__class__.__name__} Keyword Arguments Missing : content is needed to trigger message"
            )

        message_endpoint = f"{zulip_url}/api/v1/messages"
        
        # Build the payload
        payload = {
            "type": message_type,
            "to": to,
            "content": content,
        }
        
        # Topic is required for stream messages in Zulip
        if message_type == "stream":
            payload["topic"] = topic

        # Send the request using Basic Auth
        try:
            response = requests.post(
                message_endpoint,
                auth=(bot_email, bot_api_key),
                data=payload,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if hasattr(e, "response") and e.response is not None:
                error_message += f" - {e.response.text}"
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Zulip: {error_message}"
            )

        self.logger.debug("Alert message notified to Zulip")


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

    zulip_url = os.environ.get("ZULIP_URL")
    zulip_email = os.environ.get("ZULIP_BOT_EMAIL")
    zulip_api_key = os.environ.get("ZULIP_BOT_API_KEY")

    if not zulip_url or not zulip_email or not zulip_api_key:
        print("Please set ZULIP_URL, ZULIP_BOT_EMAIL, and ZULIP_BOT_API_KEY environment variables")
    else:
        # Initialize the provider and provider config
        config = ProviderConfig(
            description="Zulip Output Provider",
            authentication={
                "zulip_url": zulip_url,
                "bot_email": zulip_email,
                "bot_api_key": zulip_api_key,
            },
        )
        provider = ZulipProvider(
            context_manager, provider_id="zulip-test", config=config
        )

        provider.notify(content="Hey Zulip from Keep!", message_type="stream", to="general", topic="Alerts")
