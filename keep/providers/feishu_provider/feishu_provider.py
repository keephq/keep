"""
FeishuProvider implements the BaseOutputProvider interface for Feishu (飞书/Lark) notifications.
"""

import base64
import dataclasses
import hashlib
import hmac
import time
from typing import Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class FeishuProviderAuthConfig:
    """Feishu authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Feishu/Lark bot webhook URL",
            "sensitive": True,
            "validation": "https_url",
        }
    )
    secret: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Feishu/Lark bot signing secret (optional)",
            "sensitive": True,
        },
    )


class FeishuProvider(BaseProvider):
    """Send alert notifications to Feishu (飞书/Lark) group chats via webhook."""

    PROVIDER_DISPLAY_NAME = "Feishu"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FeishuProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _generate_sign(self, timestamp: str) -> str:
        """Generate HMAC-SHA256 signature for Feishu webhook security."""
        secret = self.authentication_config.secret
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def _notify(
        self,
        message: str = "",
        message_type: str = "text",
        title: str = "",
        **kwargs: dict,
    ):
        """
        Send a notification to Feishu/Lark via incoming webhook.

        Args:
            message (str): The message content.
            message_type (str): "text" or "post" (rich text). Defaults to "text".
            title (str): Title for rich text (post) messages.
        """
        self.logger.debug("Sending notification to Feishu")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message to send"
            )

        webhook_url = str(self.authentication_config.webhook_url)

        if message_type == "post":
            payload = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title or "Keep Alert",
                            "content": [[{"tag": "text", "text": message}]],
                        }
                    }
                },
            }
        else:
            payload = {"msg_type": "text", "content": {"text": message}}

        if self.authentication_config.secret:
            timestamp = str(int(time.time()))
            payload["timestamp"] = timestamp
            payload["sign"] = self._generate_sign(timestamp)

        response = requests.post(webhook_url, json=payload)

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: HTTP {response.status_code}"
            )

        result = response.json()
        if result.get("code") != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send notification: {result.get('msg', 'unknown error')} (code: {result.get('code')})"
            )

        self.logger.debug("Feishu notification sent successfully")
