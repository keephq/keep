"""
DingTalk (钉钉) provider is an interface for DingTalk messages.

DingTalk is Alibaba's workplace collaboration platform with 500M+ users,
widely used by Chinese enterprises. This provider sends alert notifications
to DingTalk group chats via Custom Robot Webhook.

API docs: https://open.dingtalk.com/document/robots/custom-robot-access
"""

import dataclasses
import hashlib
import hmac
import base64
import time
import urllib.parse

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DingtalkProviderAuthConfig:
    """DingTalk authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "DingTalk Custom Robot Webhook URL",
            "sensitive": True,
        },
        default="",
    )
    webhook_secret: str = dataclasses.field(
        metadata={
            "description": "DingTalk Webhook Sign Secret (optional, for signature verification)",
            "required": False,
            "sensitive": True,
        },
        default="",
    )


class DingtalkProvider(BaseProvider):
    """Send alert message to DingTalk (钉钉)."""

    PROVIDER_DISPLAY_NAME = "DingTalk"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

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
        """
        No need to dispose of anything.
        """
        pass

    def _build_signed_url(self, webhook_url: str, secret: str) -> str:
        """
        Build signed webhook URL with timestamp and sign for DingTalk bot.
        https://open.dingtalk.com/document/robots/custom-robot-access

        Args:
            webhook_url (str): The base webhook URL.
            secret (str): The webhook sign secret.

        Returns:
            str: The signed webhook URL with timestamp and sign params.
        """
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code).decode("utf-8"))
        return f"{webhook_url}&timestamp={timestamp}&sign={sign}"

    def _notify(
        self,
        message: str = "",
        title: str = "",
        msg_type: str = "markdown",
        at_mobiles: list = None,
        is_at_all: bool = False,
        **kwargs: dict,
    ):
        """
        Notify alert message to DingTalk using the Custom Robot Webhook API.

        Supports three message types:
        - "text": Simple text message
        - "markdown": Markdown formatted message (default, recommended)
        - "actionCard": Interactive card with buttons

        Args:
            message (str): The content of the message.
            title (str): The title for markdown/actionCard messages.
            msg_type (str): Message type - "text", "markdown" (default), or "actionCard".
            at_mobiles (list): List of phone numbers to @mention (for text type).
            is_at_all (bool): Whether to @all in the group.
        """
        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        self.logger.info(
            "Notifying alert message to DingTalk",
            extra={
                "msg_type": msg_type,
                "message": message[:100],
            },
        )

        webhook_url = self.authentication_config.webhook_url
        secret = self.authentication_config.webhook_secret

        # Build signed URL if secret is provided
        if secret:
            webhook_url = self._build_signed_url(webhook_url, secret)

        # Build payload based on message type
        if msg_type == "text":
            at_info = {}
            if at_mobiles:
                at_info["atMobiles"] = at_mobiles
            if is_at_all:
                at_info["isAtAll"] = is_at_all

            payload = {
                "msgtype": "text",
                "text": {
                    "content": message,
                },
            }
            if at_info:
                payload["at"] = at_info

        elif msg_type == "actionCard":
            if not title:
                title = "Keep Alert"
            # actionCard requires single/multi button action
            payload = {
                "msgtype": "actionCard",
                "actionCard": {
                    "title": title,
                    "text": message,
                },
            }
            # Support for button links if provided via kwargs
            single_url = kwargs.get("single_url", "")
            btn_orientation = kwargs.get("btn_orientation", "0")
            if single_url:
                payload["actionCard"]["singleTitle"] = title
                payload["actionCard"]["singleURL"] = single_url
            if btn_orientation != "0":
                payload["actionCard"]["btnOrientation"] = btn_orientation

        else:
            # Markdown (default)
            if not title:
                title = "Keep Alert"
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": message,
                },
            }

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to DingTalk: "
                f"HTTP {response.status_code} - {response.text}"
            )

        response_json = response.json()
        # DingTalk API returns errcode 0 for success
        if response_json.get("errcode") != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to DingTalk: "
                f"{response_json.get('errmsg', 'Unknown error')}"
            )

        self.logger.info("Alert message notified to DingTalk")
        return {"dingtalk_response": response_json}


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

    dingtalk_webhook_url = os.environ.get("DINGTALK_WEBHOOK_URL")
    dingtalk_webhook_secret = os.environ.get("DINGTALK_WEBHOOK_SECRET", "")

    config = ProviderConfig(
        description="DingTalk Output Provider",
        authentication={
            "webhook_url": dingtalk_webhook_url,
            "webhook_secret": dingtalk_webhook_secret,
        },
    )

    provider = DingtalkProvider(
        context_manager,
        provider_id="dingtalk-test",
        config=config,
    )

    provider.notify(
        message="### Keep Alert\n**High CPU usage detected** on server-01",
        title="Keep Alert",
    )
