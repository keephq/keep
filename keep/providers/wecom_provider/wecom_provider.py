"""
WeCom (企业微信) provider - Send Keep alerts to WeCom group chats via bot webhook.

WeCom is Tencent's enterprise WeChat with 250M+ active users.
API docs: https://developer.work.weixin.qq.com/document/path/91770
"""

import dataclasses
import json
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WecomProviderAuthConfig:
    """WeCom bot webhook authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeCom Bot Webhook URL (from group chat → Bot → Webhook)",
            "sensitive": True,
            "hint": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=xxx",
        },
        default="",
    )


class WecomProvider(BaseProvider):
    """Send Keep alerts to WeCom (企业微信) via Bot webhook."""

    PROVIDER_DISPLAY_NAME = "WeCom (企业微信)"
    PROVIDER_TAGS = ["messaging", "chat", "collaboration"]
    PROVIDER_CATEGORY = ["Collaboration"]
    FINGERPRINT_FIELDS = ["webhook_url"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WecomProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise Exception("WeCom webhook URL is required")

    def dispose(self):
        pass

    def _build_markdown_message(self, title: str, text: str) -> dict:
        """Build a WeCom markdown message."""
        return {
            "msgtype": "markdown",
            "markdown": {
                "content": (
                    f"## 🚨 {title}\n"
                    f"> Severity: <font color=\"warning\">Alert</font>\n\n"
                    f"{text[:4000]}"
                ),
            },
        }

    def _notify(
        self,
        message="",
        alert_name="",
        alert_message="",
        severity="info",
        **kwargs,
    ):
        """
        Send notification to WeCom chat via Bot webhook.

        Args:
            message: Fallback text if no alert_name provided
            alert_name: Alert title
            alert_message: Alert details
            severity: Alert severity (for future enhancement)
        """
        webhook_url = self.authentication_config.webhook_url

        title = alert_name or (message[:100] if message else "Keep Alert")
        body = alert_message or message or "No additional details"

        payload = self._build_markdown_message(title, body)

        self.logger.info(
            "Sending notification to WeCom",
            extra={"webhook": webhook_url[:40] + "..."},
        )

        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            if not response.ok:
                raise ProviderException(
                    f"WeCom notification failed: {response.status_code} - {response.text[:200]}"
                )

            result = response.json()
            errcode = result.get("errcode", -1)

            if errcode != 0:
                raise ProviderException(
                    f"WeCom API error: errcode={errcode}, errmsg={result.get('errmsg', '')}"
                )

            self.logger.info("WeCom notification sent successfully")

        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Network error sending WeCom notification: {e}")
