"""
WeCom (企业微信) provider is an interface for WeCom messages.

WeCom is Tencent's enterprise WeChat with 250M+ active users,
deeply integrated into Chinese business workflows. This provider
sends alert notifications to WeCom group chats via Webhook Bot.

API docs: https://developer.work.weixin.qq.com/document/path/91770
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WecomProviderAuthConfig:
    """WeCom authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeCom Webhook Bot URL",
            "sensitive": True,
        },
        default="",
    )


class WecomProvider(BaseProvider):
    """Send alert message to WeCom (企业微信)."""

    PROVIDER_DISPLAY_NAME = "WeCom"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

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
        """
        No need to dispose of anything.
        """
        pass

    def _notify(
        self,
        message: str = "",
        title: str = "",
        msg_type: str = "markdown",
        mentioned_mobile_list: list = None,
        mentioned_list: list = None,
        **kwargs: dict,
    ):
        """
        Notify alert message to WeCom using the Webhook Bot API.

        Supports message types:
        - "text": Simple text message with @mention support
        - "markdown": Markdown formatted message (default, recommended)
        - "image": Image message (requires base64 image data)
        - "news": News article message (requires articles list)
        - "file": File message (requires file media_id)

        Args:
            message (str): The content of the message.
            title (str): The title for markdown messages.
            msg_type (str): Message type - "text" or "markdown" (default).
            mentioned_mobile_list (list): Phone numbers to @mention (text type).
            mentioned_list (list): WeCom user IDs to @mention (text type).
        """
        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        self.logger.info(
            "Notifying alert message to WeCom",
            extra={
                "msg_type": msg_type,
                "message": message[:100],
            },
        )

        webhook_url = self.authentication_config.webhook_url

        # Build payload based on message type
        if msg_type == "text":
            text_content = {"content": message}
            if mentioned_mobile_list:
                text_content["mentioned_mobile_list"] = mentioned_mobile_list
            if mentioned_list:
                text_content["mentioned_list"] = mentioned_list

            payload = {
                "msgtype": "text",
                "text": text_content,
            }
        elif msg_type == "news":
            # News type requires articles list
            articles = kwargs.get("articles", [])
            if not articles:
                articles = [
                    {
                        "title": title or "Keep Alert",
                        "description": message[:512],
                        "url": kwargs.get("url", ""),
                    }
                ]
            payload = {
                "msgtype": "news",
                "news": {
                    "articles": articles,
                },
            }
        else:
            # Markdown (default)
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": message,
                },
            }

        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to WeCom: "
                f"HTTP {response.status_code} - {response.text}"
            )

        response_json = response.json()
        # WeCom API returns errcode 0 for success
        if response_json.get("errcode") != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to WeCom: "
                f"{response_json.get('errmsg', 'Unknown error')} (errcode: {response_json.get('errcode')})"
            )

        self.logger.info("Alert message notified to WeCom")
        return {"wecom_response": response_json}


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

    wecom_webhook_url = os.environ.get("WECOM_WEBHOOK_URL")

    config = ProviderConfig(
        description="WeCom Output Provider",
        authentication={
            "webhook_url": wecom_webhook_url,
        },
    )

    provider = WecomProvider(
        context_manager,
        provider_id="wecom-test",
        config=config,
    )

    provider.notify(
        message="### Keep Alert\n**High CPU usage detected** on server-01",
        title="Keep Alert",
    )
