"""
WechatProvider is a class that implements the BaseOutputProvider interface for WeChat Work (WeCom) messages.
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
    """WeChat Work authentication configuration."""

    webhook_url: HttpsUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeChat Work Group Bot Webhook URL",
            "sensitive": True,
            "validation": "https_url",
        }
    )


class WechatProvider(BaseProvider):
    """Send alert message to WeChat Work (WeCom) group chats."""

    PROVIDER_DISPLAY_NAME = "WeChat Work"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_DESCRIPTION = "Send notifications to WeChat Work (WeCom) group chats via Group Bot webhooks."

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

    def _build_payload(
        self,
        content: str = "",
        msg_type: str = "text",
        mentioned_list: list = None,
        mentioned_mobile_list: list = None,
        markdown_content: str = "",
    ) -> dict:
        """
        Build the payload for the WeChat Work webhook API.
        
        Args:
            content (str): The content of the message (for text messages).
            msg_type (str): The type of message - "text" or "markdown".
            mentioned_list (list): List of userids to mention (@all to mention everyone).
            mentioned_mobile_list (list): List of mobile numbers to mention.
            markdown_content (str): Markdown formatted content (for markdown messages).
            
        Returns:
            dict: The payload for the webhook request.
        """
        if msg_type == "markdown":
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": markdown_content or content
                }
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": content
                }
            }
            
            if mentioned_list:
                payload["text"]["mentioned_list"] = mentioned_list
            if mentioned_mobile_list:
                payload["text"]["mentioned_mobile_list"] = mentioned_mobile_list
                
        return payload

    def _notify(
        self,
        content: str = "",
        msg_type: str = "text",
        mentioned_list: list = None,
        mentioned_mobile_list: list = None,
        markdown_content: str = "",
        **kwargs: dict
    ):
        """
        Notify alert message to WeChat Work using the Group Bot Webhook API.
        https://developer.work.weixin.qq.com/document/path/90236

        Args:
            content (str): The content of the message.
            msg_type (str): Message type - "text" or "markdown".
            mentioned_list (list): List of userids to mention (use "@all" to mention everyone).
            mentioned_mobile_list (list): List of mobile numbers to mention.
            markdown_content (str): Markdown formatted content (alternative to content).
        """
        self.logger.debug("Notifying alert message to WeChat Work")
        webhook_url = self.authentication_config.webhook_url

        if not content and not markdown_content:
            raise ProviderException(
                f"{self.__class__.__name__} requires either 'content' or 'markdown_content' to send a message"
            )

        # Build the payload
        payload = self._build_payload(
            content=content,
            msg_type=msg_type,
            mentioned_list=mentioned_list or [],
            mentioned_mobile_list=mentioned_mobile_list or [],
            markdown_content=markdown_content,
        )

        # Send the request
        response = requests.post(
            webhook_url,
            json=payload,
            headers={"Content-Type": "application/json"},
        )

        # Check for errors
        if response.status_code != 200:
            raise ProviderException(
                f"{self.__class__.__name__} failed to notify: {response.status_code} - {response.text}"
            )
            
        # WeChat Work returns 200 even for errors, check the errcode
        try:
            result = response.json()
            if result.get("errcode") != 0:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to notify: {result.get('errmsg', 'Unknown error')}"
                )
        except ValueError:
            # Response is not JSON
            pass

        self.logger.debug("Alert message notified to WeChat Work")
        return result if 'result' in locals() else {"status": "success"}


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Example usage
    context_manager = ContextManager(tenant_id="test-tenant")
    config = ProviderConfig(
        authentication={"webhook_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"}
    )
    provider = WechatProvider(context_manager, "wechat-test", config)
    
    # Test text message
    provider._notify(content="Test alert from Keep!")
    
    # Test markdown message
    provider._notify(
        msg_type="markdown",
        markdown_content="**Alert**: Service is down!\n> Time: 2024-01-01 12:00:00"
    )
    
    # Test with mentions
    provider._notify(
        content="Critical alert! @all",
        mentioned_list=["@all"]
    )
