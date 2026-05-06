"""
WeComProvider is a class that implements the BaseOutputProvider interface for WeCom (企业微信) messages.
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
class WeComProviderAuthConfig:
    """WeCom authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeCom Webhook URL from the group robot settings",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class WeComProvider(BaseProvider):
    """Send alert notifications to WeCom (企业微信) group chats via webhook."""

    PROVIDER_DISPLAY_NAME = "WeCom"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WeComProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(self, message: str = "", message_type: str = "text", **kwargs: dict):
        """
        Send a notification to WeCom via incoming webhook.

        Args:
            message (str): The message content.
            message_type (str): Message type - "text" or "markdown". Defaults to "text".
        """
        self.logger.debug("Sending notification to WeCom")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message to send"
            )

        webhook_url = self.authentication_config.webhook_url

        if message_type == "markdown":
            payload = {"msgtype": "markdown", "markdown": {"content": message}}
        else:
            payload = {"msgtype": "text", "text": {"content": message}}

        response = requests.post(webhook_url, json=payload)

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: HTTP {response.status_code}"
            )

        result = response.json()
        if result.get("errcode") != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: {result.get('errmsg', 'unknown error')}"
            )

        self.logger.debug("WeCom notification sent successfully")
