"""
DingTalk (钉钉) provider - Send Keep alerts to DingTalk group chats via bot webhook.

DingTalk is Alibaba's workplace collaboration platform with 500M+ users.
API docs: https://open.dingtalk.com/document/robots/custom-robot-access
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
class DingtalkProviderAuthConfig:
    """DingTalk bot webhook authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "DingTalk Bot Webhook URL (from group chat settings → Robot → Add)",
            "sensitive": True,
            "hint": "https://oapi.dingtalk.com/robot/send?access_token=xxx",
        },
        default="",
    )
    secret: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "DingTalk bot secret for signature verification (optional)",
            "sensitive": True,
        },
        default="",
    )


class DingtalkProvider(BaseProvider):
    """Send Keep alerts to DingTalk (钉钉) via Bot webhook."""

    PROVIDER_DISPLAY_NAME = "DingTalk (钉钉)"
    PROVIDER_TAGS = ["messaging", "chat", "collaboration"]
    PROVIDER_CATEGORY = ["Collaboration"]
    FINGERPRINT_FIELDS = ["webhook_url"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DingtalkProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise Exception("DingTalk webhook URL is required")

    def dispose(self):
        pass

    def _build_markdown_message(self, title: str, text: str) -> dict:
        """Build a DingTalk markdown message."""
        return {
            "msgtype": "markdown",
            "markdown": {
                "title": title[:100],
                "text": f"## 🚨 {title}\n\n{text[:18000]}",
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
        Send notification to DingTalk chat via Bot webhook.

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
            "Sending notification to DingTalk",
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
                    f"DingTalk notification failed: {response.status_code} - {response.text[:200]}"
                )

            result = response.json()
            errcode = result.get("errcode", -1)

            if errcode != 0:
                raise ProviderException(
                    f"DingTalk API error: errcode={errcode}, errmsg={result.get('errmsg', '')}"
                )

            self.logger.info("DingTalk notification sent successfully")

        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Network error sending DingTalk notification: {e}")
