"""
Feishu (Lark) provider is an interface for Feishu messages.

Feishu is China's leading workplace collaboration platform by ByteDance,
with 600M+ daily active users. This provider sends alert notifications
to Feishu group chats via Incoming Webhook bots.

API docs: https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot
"""

import dataclasses

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
            "description": "Feishu Incoming Webhook URL",
            "sensitive": True,
        },
        default="",
    )
    webhook_secret: str = dataclasses.field(
        metadata={
            "description": "Feishu Webhook Sign Secret (optional, for signature verification)",
            "required": False,
            "sensitive": True,
        },
        default="",
    )


class FeishuProvider(BaseProvider):
    """Send alert message to Feishu (Lark)."""

    PROVIDER_DISPLAY_NAME = "Feishu"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FeishuProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise Exception("Feishu webhook URL is required")

    def dispose(self):
        """
        No need to dispose of anything.
        """
        pass

    def _build_sign(self, timestamp: str, secret: str) -> str:
        """
        Build signature for Feishu webhook with secret.
        https://open.feishu.cn/document/client-docs/bot-v3/add-custom-bot

        Args:
            timestamp (str): The timestamp string.
            secret (str): The webhook sign secret.

        Returns:
            str: The base64 encoded signature.
        """
        import hashlib
        import hmac
        import base64

        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            string_to_sign.encode("utf-8"), digestmod=hashlib.sha256
        ).digest()
        sign = base64.b64encode(hmac_code).decode("utf-8")
        return sign

    def _notify(
        self,
        message: str = "",
        title: str = "",
        msg_type: str = "interactive",
        **kwargs: dict,
    ):
        """
        Notify alert message to Feishu using the Incoming Webhook API.

        Supports two message types:
        - "text": Simple text message
        - "interactive": Rich card message (default, recommended)

        Args:
            message (str): The content of the message.
            title (str): Optional title for interactive card messages.
            msg_type (str): Message type - "text" or "interactive" (default).
        """
        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        self.logger.info(
            "Notifying alert message to Feishu",
            extra={
                "msg_type": msg_type,
                "message": message[:100],
            },
        )

        webhook_url = self.authentication_config.webhook_url
        secret = self.authentication_config.webhook_secret

        # Build payload based on message type
        if msg_type == "text":
            payload = {
                "msg_type": "text",
                "content": {
                    "text": message,
                },
            }
        else:
            # Interactive card message (default)
            card = {
                "elements": [
                    {
                        "tag": "markdown",
                        "content": message,
                    }
                ],
            }
            if title:
                card["header"] = {
                    "title": {
                        "tag": "plain_text",
                        "content": title,
                    },
                    "template": "red",
                }

            payload = {
                "msg_type": "interactive",
                "card": card,
            }

        # Add signature if secret is provided
        if secret:
            import time

            timestamp = str(int(time.time()))
            sign = self._build_sign(timestamp, secret)
            payload["timestamp"] = timestamp
            payload["sign"] = sign

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Feishu: "
                f"HTTP {response.status_code} - {response.text}"
            )

        response_json = response.json()
        # Feishu API returns code 0 for success
        if response_json.get("code") != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to Feishu: "
                f"{response_json.get('msg', 'Unknown error')}"
            )

        self.logger.info("Alert message notified to Feishu")
        return {"feishu_response": response_json}


if __name__ == "__main__":
    # Output debug messages
    import logging
    import os

    from keep.providers.providers_factory import ProvidersFactory

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    feishu_webhook_url = os.environ.get("FEISHU_WEBHOOK_URL")
    feishu_webhook_secret = os.environ.get("FEISHU_WEBHOOK_SECRET", "")

    config = ProviderConfig(
        description="Feishu Output Provider",
        authentication={
            "webhook_url": feishu_webhook_url,
            "webhook_secret": feishu_webhook_secret,
        },
    )

    provider = FeishuProvider(
        context_manager,
        provider_id="feishu-test",
        config=config,
    )

    provider.notify(
        message="**Alert:** High CPU usage detected on server-01",
        title="Keep Alert",
    )
