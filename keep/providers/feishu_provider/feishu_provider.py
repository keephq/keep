"""
Feishu (飞书/Lark) provider - Send Keep alerts to Feishu group chats via bot webhook.

Feishu is China's leading workplace collaboration platform (600M+ DAU).
This provider follows the same pattern as Slack/Discord/Telegram providers.

Docs: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
"""

import dataclasses
import json
import os
import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FeishuProviderAuthConfig:
    """Feishu bot webhook authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Feishu Bot Webhook URL (from Feishu group chat → Bot → Webhook)",
            "sensitive": True,
            "hint": "https://open.feishu.cn/open-apis/bot/v2/hook/xxx",
        },
        default="",
    )


class FeishuProvider(BaseProvider):
    """Send Keep alerts to Feishu (飞书) via Bot webhook."""

    PROVIDER_DISPLAY_NAME = "Feishu (飞书)"
    PROVIDER_TAGS = ["messaging", "chat", "collaboration"]
    PROVIDER_CATEGORY = ["Collaboration"]
    
    FINGERPRINT_FIELDS = ["webhook_url"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validate that webhook_url is provided."""
        self.authentication_config = FeishuProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise Exception("Feishu webhook URL is required")

    def dispose(self):
        """No cleanup needed."""
        pass

    def _build_message_card(self, alert_name: str, alert_message: str, 
                            severity: str = "info", extra_info: dict = None) -> dict:
        """
        Build a Feishu interactive card message.
        
        Returns a Feishu card message dict that renders as a rich card in chat.
        """
        # Color mapping for severity
        colors = {
            "critical": "red",
            "warning": "yellow",
            "info": "blue",
        }
        
        elements = [
            {
                "tag": "markdown",
                "content": alert_message[:4000],  # Feishu limits
            }
        ]
        
        if extra_info:
            fields = []
            for key, value in extra_info.items():
                fields.append({
                    "is_short": True,
                    "text": {
                        "tag": "lark_md",
                        "content": f"**{key}**\n{value}"
                    }
                })
            if fields:
                elements.insert(0, {
                    "tag": "div",
                    "fields": fields[:10],  # Max 10 fields
                })
        
        card = {
            "config": {"wide_screen_mode": True},
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"🚨 {alert_name}"
                },
                "template": colors.get(severity, "blue"),
            },
            "elements": elements,
        }
        
        return {
            "msg_type": "interactive",
            "card": card,
        }

    def _notify(
        self,
        message="",
        alert_name="",
        alert_message="",
        severity="info",
        use_card=True,
        **kwargs,
    ):
        """
        Send notification to Feishu chat via Bot webhook.

        Args:
            message: Plain text message (used if use_card=False)
            alert_name: Name of the alert for card title
            alert_message: Alert details for card body
            severity: Alert severity (critical, warning, info)
            use_card: Send as rich interactive card (True) or plain text (False)
        """
        webhook_url = self.authentication_config.webhook_url
        
        if use_card:
            # Build extra info from kwargs
            extra = {}
            for key in ["source", "service", "status", "timestamp", "description"]:
                if key in kwargs and kwargs[key]:
                    extra[key.capitalize()] = str(kwargs[key])[:100]
            
            # Use alert_name/alert_message from kwargs if not provided directly
            name = alert_name or message[:50] if message else "Keep Alert"
            msg = alert_message or message or "No additional details"
            
            payload = self._build_message_card(name, msg, severity, extra)
        else:
            # Simple text message
            text = message or f"Keep Alert: {alert_name}"
            payload = {
                "msg_type": "text",
                "content": {
                    "text": text[:20000],  # Feishu text limit
                },
            }
        
        self.logger.info(
            "Sending notification to Feishu",
            extra={"webhook": webhook_url[:30] + "..."},
        )
        
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            
            if not response.ok:
                self.logger.error(
                    "Failed to send Feishu notification",
                    extra={
                        "status_code": response.status_code,
                        "response": response.text[:500],
                    },
                )
                raise ProviderException(
                    f"Failed to send Feishu notification: {response.status_code} - {response.text[:200]}"
                )
            
            result = response.json()
            code = result.get("code", -1)
            msg = result.get("msg", "")
            
            if code != 0:
                self.logger.error(
                    "Feishu API returned error",
                    extra={"code": code, "msg": msg},
                )
                raise ProviderException(
                    f"Feishu API error: code={code}, msg={msg}"
                )
            
            self.logger.info("Feishu notification sent successfully")
            
        except requests.exceptions.RequestException as e:
            self.logger.error(
                "Network error sending Feishu notification",
                extra={"error": str(e)},
            )
            raise ProviderException(f"Network error sending Feishu notification: {e}")
