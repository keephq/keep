"""
Feishu Provider is a class that implements the BaseOutputProvider interface for Feishu (Lark) messages.
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

    webhook_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Feishu Bot Webhook Token",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )


class FeishuProvider(BaseProvider):
    """Send alert message to Feishu (Lark) via custom bot webhook."""

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

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def validate_scopes(self):
        """
        Validate that the webhook token is valid by making a test request.
        """
        try:
            self._send_message("Keep test message")
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(
        self,
        message: str,
    ):
        """
        Send a message to Feishu via custom bot webhook.
        https://open.feishu.cn/document/ukTMukTMukTM/ucTM5ejL3ETO14yNxkTN
        """
        webhook_token = self.authentication_config.webhook_token

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        headers = {
            "Content-Type": "application/json",
        }

        payload = {
            "msg_type": "text",
            "content": {
                "text": message,
            },
        }

        response = requests.post(
            f"https://open.feishu.cn/open-apis/bot/v2/hook/{webhook_token}",
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("code") != 0:
                raise ProviderException(
                    f"{self.__class__.__name__} failed to send message: {result.get('msg', 'Unknown error')}"
                )
            return result
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
        **kwargs: dict,
    ):
        """
        Notify alert message to Feishu.

        Args:
            message (str): The message to send.
        """
        self.logger.debug("Notifying alert message to Feishu")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(message=message)

        self.logger.debug("Alert message notified to Feishu")
        return {"message": message, "status": result.get("msg"), "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    feishu_webhook_token = os.environ.get("FEISHU_WEBHOOK_TOKEN")

    if feishu_webhook_token is None:
        raise Exception("FEISHU_WEBHOOK_TOKEN is required")

    config = ProviderConfig(
        description="Feishu Output Provider",
        authentication={"webhook_token": feishu_webhook_token},
    )
    provider = FeishuProvider(
        context_manager, provider_id="feishu-test", config=config
    )

    provider.notify(message="Hello from Keep!")
