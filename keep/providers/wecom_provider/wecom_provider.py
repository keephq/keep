"""
WecomProvider is a class that allows sending notifications to WeCom (Enterprise WeChat) groups
via the WeCom Group Bot Webhook API.
"""

import dataclasses
import logging
from typing import Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class WecomProviderAuthConfig:
    """
    WeCom (Enterprise WeChat) Group Bot authentication configuration.

    Obtain the Webhook URL by:
    1. Opening a group in WeCom (企业微信).
    2. Clicking the three-dot menu → Add Group Bot → Create a Bot.
    3. Copying the Webhook URL shown after creation.

    Reference: https://developer.work.weixin.qq.com/document/path/90236
    """

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeCom Group Bot Webhook URL",
            "hint": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class WecomProvider(BaseProvider):
    """Send alert notifications to WeCom (Enterprise WeChat) group chats via a Group Bot Webhook."""

    PROVIDER_DISPLAY_NAME = "WeCom"
    PROVIDER_CATEGORY = ["Collaboration"]

    # WeCom webhook endpoint (same for all bots; the key is embedded in the URL)
    WECOM_API_BASE = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WecomProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _notify(
        self,
        message: str = "",
        message_type: str = "markdown",
        mentioned_list: Optional[list] = None,
        mentioned_mobile_list: Optional[list] = None,
        **kwargs,
    ):
        """
        Send a message to a WeCom group via the Group Bot Webhook.

        Args:
            message (str): The message content. Supports Markdown when message_type="markdown".
            message_type (str): "text" or "markdown" (default: "markdown").
            mentioned_list (list): List of WeCom userids to @mention, or ["@all"] to mention everyone.
            mentioned_mobile_list (list): List of phone numbers to @mention.

        Reference: https://developer.work.weixin.qq.com/document/path/90236
        """
        if not message:
            raise ProviderException("WecomProvider: 'message' is required")

        if message_type not in ("text", "markdown"):
            self.logger.warning(
                "WecomProvider: unsupported message_type '%s', falling back to 'text'",
                message_type,
            )
            message_type = "text"

        if message_type == "markdown":
            payload: dict = {
                "msgtype": "markdown",
                "markdown": {"content": message},
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": message,
                    "mentioned_list": mentioned_list or [],
                    "mentioned_mobile_list": mentioned_mobile_list or [],
                },
            }

        self.logger.debug("Sending WeCom message", extra={"type": message_type})

        response = requests.post(
            str(self.authentication_config.webhook_url),
            json=payload,
            timeout=10,
        )

        if response.status_code != 200:
            raise ProviderException(
                f"WecomProvider: HTTP {response.status_code} — {response.text}"
            )

        resp_json = response.json()
        if resp_json.get("errcode", 0) != 0:
            raise ProviderException(
                f"WecomProvider: WeCom API error {resp_json.get('errcode')} — "
                f"{resp_json.get('errmsg', 'unknown error')}"
            )

        self.logger.debug("WeCom message sent successfully")


if __name__ == "__main__":
    import os
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    webhook_url = os.environ.get("WECOM_WEBHOOK_URL")
    if not webhook_url:
        raise ValueError("WECOM_WEBHOOK_URL environment variable is required")

    config = ProviderConfig(
        description="WeCom Output Provider",
        authentication={"webhook_url": webhook_url},
    )
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")
    provider = WecomProvider(context_manager, provider_id="wecom-test", config=config)
    provider.notify(
        message="## Keep Alert\n**Status:** FIRING\n**Severity:** Critical\n\nThis is a test alert from Keep.",
        message_type="markdown",
    )
