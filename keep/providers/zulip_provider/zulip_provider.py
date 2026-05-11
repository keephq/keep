"""
Zulip Provider is a class that implements the BaseOutputProvider interface for Zulip messages.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class ZulipProviderAuthConfig:
    """Zulip authentication configuration."""

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip bot API key",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )
    zulip_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip server URL (e.g. https://zulip.example.com)",
            "config_main_group": "authentication",
        }
    )
    email: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Zulip bot email address",
            "config_main_group": "authentication",
        }
    )


class ZulipProvider(BaseProvider):
    """Send alert message to Zulip."""

    PROVIDER_DISPLAY_NAME = "Zulip"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

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

    def validate_scopes(self):
        """
        Validate that the credentials are valid by making a test request.
        """
        try:
            self._send_message("Keep test message")
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(
        self,
        message: str,
        to: str = None,
        topic: str = "alerts",
        type: str = "stream",
    ):
        """
        Send a message to Zulip.
        https://zulip.com/api/send-message
        """
        api_key = self.authentication_config.api_key
        zulip_url = self.authentication_config.zulip_url.rstrip("/")
        email = self.authentication_config.email

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        if not to:
            raise ProviderException(
                f"{self.__class__.__name__} 'to' (stream name or user email) is required"
            )

        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }

        payload = {
            "type": type,
            "to": to,
            "content": message,
        }

        if type == "stream":
            payload["topic"] = topic

        response = requests.post(
            f"{zulip_url}/api/v1/messages",
            auth=(email, api_key),
            headers=headers,
            data=payload,
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()
        elif response.status_code == 401:
            raise ProviderException(
                f"{self.__class__.__name__} unauthorized - invalid API key or email"
            )
        elif response.status_code == 400:
            raise ProviderException(
                f"{self.__class__.__name__} bad request - {response.text}"
            )
        else:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: {response.status_code} - {response.text}"
            )

    def _notify(
        self,
        message: str = "",
        to: str = None,
        topic: str = "alerts",
        type: str = "stream",
        **kwargs: dict,
    ):
        """
        Notify alert message to Zulip.

        Args:
            message (str): The message content (supports Markdown).
            to (str): Stream name (for stream messages) or user email (for private messages).
            topic (str): Topic name for stream messages (default: "alerts").
            type (str): Message type - "stream" or "private" (default: "stream").
        """
        self.logger.debug("Notifying alert message to Zulip")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(
            message=message,
            to=to,
            topic=topic,
            type=type,
        )

        self.logger.debug("Alert message notified to Zulip")
        return {"message": message, "id": result.get("id"), "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    zulip_api_key = os.environ.get("ZULIP_API_KEY")
    zulip_url = os.environ.get("ZULIP_URL")
    zulip_email = os.environ.get("ZULIP_EMAIL")

    if zulip_api_key is None or zulip_url is None or zulip_email is None:
        raise Exception("ZULIP_API_KEY, ZULIP_URL and ZULIP_EMAIL are required")

    config = ProviderConfig(
        description="Zulip Output Provider",
        authentication={
            "api_key": zulip_api_key,
            "zulip_url": zulip_url,
            "email": zulip_email,
        },
    )
    provider = ZulipProvider(
        context_manager, provider_id="zulip-test", config=config
    )

    provider.notify(message="Hello from Keep!", to="general")
