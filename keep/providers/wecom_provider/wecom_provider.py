"""
WeCom Provider is a class that implements the BaseOutputProvider interface for WeCom (企业微信) messages.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class WeComProviderAuthConfig:
    """WeCom authentication configuration."""

    webhook_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "WeCom Group Robot Webhook Key",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )


class WeComProvider(BaseProvider):
    """Send alert message to WeCom (企业微信)."""

    PROVIDER_DISPLAY_NAME = "WeCom"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = WeComProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def validate_scopes(self):
        """
        Validate that the webhook key is valid by making a test request.
        """
        try:
            self._send_message("Keep test message")
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(
        self,
        message: str,
        markdown: bool = False,
        mentioned_mobile_list: list = None,
    ):
        """
        Send a message to WeCom via group robot webhook.
        https://developer.work.weixin.qq.com/document/path/91770
        """
        webhook_key = self.authentication_config.webhook_key

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        url = f"https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key={webhook_key}"

        headers = {
            "Content-Type": "application/json",
        }

        if markdown:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "content": message,
                },
            }
        else:
            payload = {
                "msgtype": "text",
                "text": {
                    "content": message,
                },
            }
            if mentioned_mobile_list:
                payload["text"]["mentioned_mobile_list"] = mentioned_mobile_list

        response = requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("errcode") == 0:
                return result
            else:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send message: {result.get('errcode')} - {result.get('errmsg')}"
                )
        elif response.status_code == 401:
            raise ProviderException(
                f"{self.__class__.__name__} unauthorized - invalid webhook key"
            )
        elif response.status_code == 400:
            raise ProviderException(
                f"{self.__class__.__name__} bad request - {response.text}"
            )
        else:
            raise ProviderException(
                f"{self.__class__.__name__} failed to send message: {response.status_code} - {response.text}"
            )

    def _notify(
        self,
        message: str = "",
        markdown: bool = False,
        mentioned_mobile_list: list = None,
        **kwargs: dict,
    ):
        """
        Notify alert message to WeCom.

        Args:
            message (str): The message text to send.
            markdown (bool): If True, send the message as markdown.
            mentioned_mobile_list (list): List of mobile numbers to @mention in the group.
        """
        self.logger.debug("Notifying alert message to WeCom")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(
            message=message,
            markdown=markdown,
            mentioned_mobile_list=mentioned_mobile_list,
        )

        self.logger.debug("Alert message notified to WeCom")
        return {"message": message, "status": result.get("errcode"), "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    wecom_webhook_key = os.environ.get("WECOM_WEBHOOK_KEY")

    if wecom_webhook_key is None:
        raise Exception("WECOM_WEBHOOK_KEY is required")

    config = ProviderConfig(
        description="WeCom Output Provider",
        authentication={"webhook_key": wecom_webhook_key},
    )
    provider = WeComProvider(
        context_manager, provider_id="wecom-test", config=config
    )

    provider.notify(message="Hello from Keep!")
