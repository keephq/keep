"""
Feishu (飞书/Lark) provider is an interface for Feishu bot notifications.
"""

import dataclasses
import hashlib
import hmac
import json
import time
import base64

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class FeishuProviderAuthConfig:
    """Feishu authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Feishu Bot Webhook URL",
            "sensitive": True,
        },
        default="",
    )
    webhook_secret: str = dataclasses.field(
        metadata={
            "description": "Feishu Bot Webhook Sign Secret (optional, for message verification)",
            "required": False,
            "sensitive": True,
        },
        default="",
    )


class FeishuProvider(BaseProvider):
    """Send alert notifications to Feishu (飞书/Lark) group chats via bot webhook."""

    PROVIDER_DISPLAY_NAME = "Feishu"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["alert", "notification"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FeishuProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise ProviderException("Feishu webhook URL is required")

    def dispose(self):
        pass

    def _generate_sign(self, secret: str, timestamp: str) -> str:
        """Generate sign for webhook verification (optional security feature).
        
        Feishu sign algorithm: 
        timestamp + "\n" + secret → SHA256 HMAC → base64 encode
        """
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return sign

    def _notify(self, **kwargs) -> dict:
        """Send notification to Feishu group chat via bot webhook.

        Supports:
        - text: simple text message
        - rich_text: interactive card message (default)
        - @mention: mention specific users
        """
        message_type = kwargs.get("message_type", "interactive")
        message = kwargs.get("message", "")
        title = kwargs.get("title", "Keep Alert")
        
        if not message:
            message = self._format_alert_message()

        timestamp = str(int(time.time()))

        # Build payload
        if message_type == "text":
            payload = {
                "msg_type": "text",
                "content": {
                    "text": message
                }
            }
        elif message_type == "interactive":
            # Rich card format (Feishu interactive card)
            payload = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": title
                        },
                        "template": "red"  # alert style
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "plain_text",
                                "content": message
                            }
                        }
                    ]
                }
            }
        elif message_type == "post":
            # Rich text post format
            payload = {
                "msg_type": "post",
                "content": {
                    "post": {
                        "zh_cn": {
                            "title": title,
                            "content": [
                                [
                                    {
                                        "tag": "text",
                                        "text": message
                                    }
                                ]
                            ]
                        }
                    }
                }
            }
        else:
            payload = {
                "msg_type": "text",
                "content": {
                    "text": message
                }
            }

        # Add sign if secret is configured
        if self.authentication_config.webhook_secret:
            sign = self._generate_sign(
                self.authentication_config.webhook_secret, timestamp
            )
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        # Send to Feishu webhook
        response = requests.post(
            self.authentication_config.webhook_url,
            json=payload,
            timeout=30,
        )

        if response.status_code != 200:
            raise ProviderException(
                f"Failed to send Feishu notification: {response.status_code} {response.text}"
            )

        result = response.json()
        # Feishu returns {"code": 0} for success
        if result.get("code") != 0:
            raise ProviderException(
                f"Feishu API error: code={result.get('code')}, msg={result.get('msg', 'unknown error')}"
            )

        return result

    def _format_alert_message(self) -> str:
        """Format alert data into a readable message."""
        alert = self.context_manager.alert_data
        if not alert:
            return "Alert notification from Keep"

        name = alert.get("name", "Unknown Alert")
        severity = alert.get("severity", "unknown")
        description = alert.get("description", "No description")
        source = alert.get("source", ["unknown"])
        if isinstance(source, list):
            source = source[0] if source else "unknown"

        return f"[{severity.upper()}] {name}\nSource: {source}\n{description}"

    @staticmethod
    def _format_alert_to_feishu_card(alert: dict) -> dict:
        """Format an alert into a Feishu interactive card."""
        severity = alert.get("severity", "unknown")
        name = alert.get("name", "Unknown Alert")
        description = alert.get("description", "No description")

        # Color mapping for severity
        color_map = {
            "critical": "red",
            "high": "orange",
            "warning": "yellow",
            "info": "blue",
            "low": "green",
        }
        template = color_map.get(severity.lower(), "red")

        return {
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": f"[{severity.upper()}] {name}"
                },
                "template": template
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "plain_text",
                        "content": description
                    }
                }
            ]
        }


if __name__ == "__main__":
    # For local testing
    import os

    context_manager = ContextManager(
        tenant_id="test",
        workflow_id="test",
    )
    
    config = ProviderConfig(
        authentication={
            "webhook_url": os.environ.get("FEISHU_WEBHOOK_URL", ""),
            "webhook_secret": os.environ.get("FEISHU_WEBHOOK_SECRET", ""),
        },
    )
    
    provider = FeishuProvider(
        context_manager=context_manager,
        provider_id="feishu-test",
        config=config,
    )
    
    result = provider.notify(
        message="Test alert from Keep",
        title="Keep Test Alert",
        message_type="interactive",
    )
    
    print(f"Result: {result}")