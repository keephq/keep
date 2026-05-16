"""
WeCom (企业微信) provider is an interface for WeCom bot notifications.
"""

import dataclasses
import hashlib
import hmac
import base64
import json
import time

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WeComProviderAuthConfig:
    """WeCom authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeCom Bot Webhook URL",
            "sensitive": True,
        },
        default="",
    )


class WeComProvider(BaseProvider):
    """Send alert notifications to WeCom (企业微信) group chats via bot webhook."""

    PROVIDER_DISPLAY_NAME = "WeCom"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["alert", "notification"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WeComProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise ProviderException("WeCom webhook URL is required")

    def dispose(self):
        pass

    def _notify(self, **kwargs) -> dict:
        """Send notification to WeCom group chat via bot webhook.

        Supports:
        - text: simple text message
        - markdown: markdown formatted message (default)
        - image: base64 image message
        """
        message_type = kwargs.get("message_type", "markdown")
        message = kwargs.get("message", "")
        title = kwargs.get("title", "Keep Alert")
        mentioned_list = kwargs.get("mentioned_list", [])

        if not message:
            message = self._format_alert_message()

        if message_type == "text":
            payload = {
                "msgtype": "text",
                "text": {
                    "content": message,
                    "mentioned_list": mentioned_list if mentioned_list else [],
                }
            }
        elif message_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": f"### {title}\n\n{message}"
                }
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {"content": message}
            }

        response = requests.post(
            self.authentication_config.webhook_url,
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            raise ProviderException(
                f"Failed to send WeCom notification: {response.status_code} {response.text}"
            )

        result = response.json()
        if result.get("errcode") != 0:
            raise ProviderException(
                f"WeCom API error: errcode={result.get('errcode')}, errmsg={result.get('errmsg', 'unknown error')}"
            )

        return result

    def _format_alert_message(self) -> str:
        """Format alert data into a readable markdown message."""
        alert = self.context_manager.alert_data
        if not alert:
            return "Alert notification from Keep"

        name = alert.get("name", "Unknown Alert")
        severity = alert.get("severity", "unknown")
        description = alert.get("description", "No description")

        emoji_map = {
            "critical": "🔴",
            "high": "🟠",
            "warning": "🟡",
            "info": "🔵",
            "low": "🟢",
        }
        emoji = emoji_map.get(severity.lower(), "⚠️")

        return f"{emoji} **[{severity.upper()}]** {name}\n\n{description}"


if __name__ == "__main__":
    import os

    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "webhook_url": os.environ.get("WECOM_WEBHOOK_URL", ""),
        },
    )
    provider = WeComProvider(
        context_manager=context_manager,
        provider_id="wecom-test",
        config=config,
    )
    result = provider.notify(message="Test alert from Keep", title="Keep Test Alert")
    print(f"Result: {result}")