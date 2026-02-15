"""
WechatProvider is a class that implements the BaseOutputProvider interface for WeChat (WeCom) messages.
"""

import dataclasses
import pydantic
import requests
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.validation.fields import HttpsUrl


@pydantic.dataclasses.dataclass
class WechatProviderAuthConfig:
    """WeChat (WeCom) authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeCom Webhook Url",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class WechatProvider(BaseProvider):
    """Send alert message to WeChat (WeCom)."""

    PROVIDER_DISPLAY_NAME = "WeChat"
    PROVIDER_CATEGORY = ["Collaboration"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WechatProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def _notify(self, content: str = "", msg_type: str = "markdown", **kwargs: dict):
        """
        Notify alert message to WeChat using the WeCom Incoming Webhook API
        https://developer.work.weixin.qq.com/document/path/90236

        Args:
            content (str): The content of the message.
            msg_type (str): The type of the message (text or markdown). Defaults to markdown.
        """
        self.logger.debug("Notifying alert message to WeChat")
        webhook_url = self.authentication_config.webhook_url

        if not content:
            raise ProviderException(
                f"{self.__class__.__name__} Keyword Arguments Missing : content is required"
            )

        if msg_type not in ["text", "markdown"]:
            self.logger.warning(
                f"Invalid msg_type {msg_type} for WeChat provider, defaulting to markdown"
            )
            msg_type = "markdown"

        # send the request
        payload = {
            "msgtype": msg_type,
            msg_type: {"content": content},
        }
        
        # Add mentioned list if provided
        mentioned_list = kwargs.get("mentioned_list")
        if mentioned_list and msg_type == "text":
            payload["text"]["mentioned_list"] = mentioned_list
            
        mentioned_mobile_list = kwargs.get("mentioned_mobile_list")
        if mentioned_mobile_list and msg_type == "text":
            payload["text"]["mentioned_mobile_list"] = mentioned_mobile_list

        response = requests.post(
            webhook_url,
            json=payload,
        )

        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to WeChat: {response.text}"
            )
            
        result = response.json()
        if result.get("errcode") != 0:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify alert message to WeChat (errcode={result.get('errcode')}): {result.get('errmsg')}"
            )

        self.logger.debug("Alert message notified to WeChat")


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    wechat_webhook_url = os.environ.get("WECHAT_WEBHOOK_URL")

    # Initalize the provider and provider config
    config = ProviderConfig(
        description="WeChat Output Provider",
        authentication={"webhook_url": wechat_webhook_url},
    )
    provider = WechatProvider(
        context_manager, provider_id="wechat-test", config=config
    )

    provider.notify(
        content="Hey WeChat from Keep!", msg_type="markdown"
    )
