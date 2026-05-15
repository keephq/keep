"""
DingTalk (钉钉) provider is an interface for DingTalk bot notifications.
"""

import dataclasses
import hashlib
import hmac
import base64
import json
import time
import urllib.parse

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DingTalkProviderAuthConfig:
    """DingTalk authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "DingTalk Bot Webhook URL",
            "sensitive": True,
        },
        default="",
    )
    secret: str = dataclasses.field(
        metadata={
            "description": "DingTalk Bot Sign Secret (optional, for message verification)",
            "required": False,
            "sensitive": True,
        },
        default="",
    )


class DingTalkProvider(BaseProvider):
    """Send alert notifications to DingTalk (钉钉) group chats via bot webhook."""

    PROVIDER_DISPLAY_NAME = "DingTalk"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["alert", "notification"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DingTalkProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise ProviderException("DingTalk webhook URL is required")

    def dispose(self):
        pass

    def _generate_sign(self, secret: str) -> tuple:
        """Generate sign for DingTalk webhook verification.

        DingTalk sign algorithm:
        timestamp + "\n" + secret → HMAC-SHA256 → base64 encode → URL encode

        Returns:
            tuple: (timestamp, sign)
        """
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
        return timestamp, sign

    def _get_webhook_url(self) -> str:
        """Get webhook URL with optional sign parameters."""
        url = self.authentication_config.webhook_url
        if self.authentication_config.secret:
            timestamp, sign = self._generate_sign(self.authentication_config.secret)
            separator = "&" if "?" in url else "?"
            url = f"{url}{separator}timestamp={timestamp}&sign={sign}"
        return url

    def _notify(self, **kwargs) -> dict:
        """Send notification to DingTalk group chat via bot webhook.

        Supports:
        - text: simple text message
        - markdown: markdown formatted message (default)
        - actionCard: card with action links
        """
        message_type = kwargs.get("message_type", "markdown")
        message = kwargs.get("message", "")
        title = kwargs.get("title", "Keep Alert")

        if not message:
            message = self._format_alert_message()

        # Build payload based on message type
        if message_type == "text":
            payload = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }
        elif message_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"### {title}\n\n{message}"
                }
            }
        elif message_type == "actionCard":
            action_url = kwargs.get("action_url", "")
            action_title = kwargs.get("action_title", "View Details")
            btns = []
            if action_url:
                btns.append({
                    "title": action_title,
                    "actionURL": action_url
                })
            payload = {
                "msgtype": "actionCard",
                "actionCard": {
                    "title": title,
                    "text": message,
                    "btns": btns
                }
            }
        else:
            # Default to text
            payload = {
                "msgtype": "text",
                "text": {
                    "content": message
                }
            }

        # Get webhook URL with sign if configured
        url = self._get_webhook_url()

        # Send to DingTalk webhook
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30,
        )

        if response.status_code != 200:
            raise ProviderException(
                f"Failed to send DingTalk notification: {response.status_code} {response.text}"
            )

        result = response.json()
        # DingTalk returns {"errcode": 0, "errmsg": "ok"} for success
        if result.get("errcode") != 0:
            raise ProviderException(
                f"DingTalk API error: errcode={result.get('errcode')}, errmsg={result.get('errmsg', 'unknown error')}"
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
        source = alert.get("source", ["unknown"])
        if isinstance(source, list):
            source = source[0] if source else "unknown"

        # Emoji for severity
        emoji_map = {
            "critical": "🔴",
            "high": "🟠",
            "warning": "🟡",
            "info": "🔵",
            "low": "🟢",
        }
        emoji = emoji_map.get(severity.lower(), "⚠️")

        return f"{emoji} **[{severity.upper()}]** {name}\n\n> Source: {source}\n\n{description}"


if __name__ == "__main__":
    # For local testing
    import os

    context_manager = ContextManager(
        tenant_id="test",
        workflow_id="test",
    )

    config = ProviderConfig(
        authentication={
            "webhook_url": os.environ.get("DINGTALK_WEBHOOK_URL", ""),
            "secret": os.environ.get("DINGTALK_SECRET", ""),
        },
    )

    provider = DingTalkProvider(
        context_manager=context_manager,
        provider_id="dingtalk-test",
        config=config,
    )

    result = provider.notify(
        message="Test alert from Keep",
        title="Keep Test Alert",
        message_type="markdown",
    )

    print(f"Result: {result}")