"""
LineNotifyProvider is a class that implements the BaseOutputProvider interface for LINE Notify messages.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LineNotifyProviderAuthConfig:
    """LINE Notify authentication configuration."""

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "LINE Notify Personal Access Token",
            "sensitive": True,
        }
    )


class LineNotifyProvider(BaseProvider):
    """Send alert message to LINE Notify."""

    PROVIDER_DISPLAY_NAME = "LINE Notify"
    PROVIDER_CATEGORY = ["Messaging"]

    # LINE Notify API endpoint is fixed
    LINE_NOTIFY_API_URL = "https://notify-api.line.me/api/notify"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LineNotifyProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, content: str = "", **kwargs: dict):
        """
        Notify alert message to LINE using the LINE Notify API
        https://notify-bot.line.me/doc/en/

        Args:
            content (str): The content of the message.
        """
        self.logger.debug("Notifying alert message to LINE Notify")
        access_token = self.authentication_config.access_token

        if not content:
            raise ProviderException(
                f"{self.__class__.__name__} Keyword Arguments Missing : content is needed to trigger message"
            )

        headers = {
            "Authorization": f"Bearer {access_token}"
        }
        
        # LINE Notify expects form-urlencoded payload
        payload = {
            "message": content
        }

        # Send the request
        try:
            response = requests.post(
                self.LINE_NOTIFY_API_URL,
                headers=headers,
                data=payload,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            error_message = str(e)
            if hasattr(e, "response") and e.response is not None:
                error_message += f" - {e.response.text}"
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to LINE Notify: {error_message}"
            )

        self.logger.debug("Alert message notified to LINE Notify")


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

    line_token = os.environ.get("LINE_NOTIFY_ACCESS_TOKEN")

    if not line_token:
        print("Please set LINE_NOTIFY_ACCESS_TOKEN environment variable")
    else:
        # Initialize the provider and provider config
        config = ProviderConfig(
            description="LINE Notify Output Provider",
            authentication={"access_token": line_token},
        )
        provider = LineNotifyProvider(
            context_manager, provider_id="line-notify-test", config=config
        )

        provider.notify(content="Hey LINE Notify from Keep!")
