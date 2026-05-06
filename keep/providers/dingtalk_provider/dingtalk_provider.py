"""
DingTalkProvider implements the BaseOutputProvider interface for DingTalk (钉钉) notifications.
"""

import base64
import dataclasses
import hashlib
import hmac
import time
from typing import Optional
from urllib.parse import quote

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class DingTalkProviderAuthConfig:
    """DingTalk authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "DingTalk robot webhook URL",
            "sensitive": True,
            "validation": "https_url",
        }
    )
    secret: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "DingTalk robot signing secret (optional, for sign verification)",
            "sensitive": True,
        },
    )


class DingTalkProvider(BaseProvider):
    """Send alert notifications to DingTalk (钉钉) group chats via webhook."""

    PROVIDER_DISPLAY_NAME = "DingTalk"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DingTalkProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _get_signed_url(self) -> str:
        """Return webhook URL with HMAC-SHA256 signature if secret is configured."""
        webhook_url = str(self.authentication_config.webhook_url)
        secret = self.authentication_config.secret
        if not secret:
            return webhook_url

        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"), string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        sign = quote(base64.b64encode(hmac_code))
        return f"{webhook_url}&timestamp={timestamp}&sign={sign}"

    def _notify(self, message: str = "", title: str = "Keep Alert", message_type: str = "text", at_all: bool = False, **kwargs: dict):
        """
        Send a notification to DingTalk via incoming webhook.

        Args:
            message (str): The message content.
            title (str): Title for markdown messages.
            message_type (str): "text" or "markdown". Defaults to "text".
            at_all (bool): Whether to @mention all members. Defaults to False.
        """
        self.logger.debug("Sending notification to DingTalk")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message to send"
            )

        url = self._get_signed_url()

        if message_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {"title": title, "text": message},
                "at": {"isAtAll": at_all},
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {"content": message},
                "at": {"isAtAll": at_all},
            }

        response = requests.post(url, json=payload)

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: HTTP {response.status_code}"
            )

        result = response.json()
        if result.get("errcode") != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: {result.get('errmsg', 'unknown error')} (errcode: {result.get('errcode')})"
            )

        self.logger.debug("DingTalk notification sent successfully")
