"""
DingTalk Provider is a class that implements the BaseOutputProvider interface for DingTalk messages.
"""

import base64
import dataclasses
import hashlib
import hmac
import time
import urllib.parse

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class DingTalkProviderAuthConfig:
    """DingTalk authentication configuration."""

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "DingTalk Robot Access Token",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )
    secret: str = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "DingTalk Robot Secret (for signature verification)",
            "sensitive": True,
            "config_main_group": "authentication",
        },
    )


class DingTalkProvider(BaseProvider):
    """Send alert message to DingTalk."""

    PROVIDER_DISPLAY_NAME = "DingTalk"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = DingTalkProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """
        No need to dispose of anything, so just do nothing.
        """
        pass

    def validate_scopes(self):
        """
        Validate that the access token is valid by making a test request.
        """
        try:
            self._send_message("Keep test message")
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _generate_sign(self, secret: str) -> tuple[str, str]:
        """
        Generate DingTalk webhook signature.
        Returns (timestamp, signature).
        """
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(
            secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def _send_message(
        self,
        message: str,
        title: str = None,
        msgtype: str = "text",
        at_mobiles: list = None,
        at_userids: list = None,
        is_at_all: bool = False,
    ):
        """
        Send a message to DingTalk via webhook robot.
        https://open.dingtalk.com/document/robots/custom-robot-access
        """
        access_token = self.authentication_config.access_token
        secret = self.authentication_config.secret

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        if msgtype not in ["text", "markdown"]:
            raise ProviderException(
                f"{self.__class__.__name__} msgtype must be 'text' or 'markdown'"
            )

        params = {"access_token": access_token}

        if secret:
            timestamp, sign = self._generate_sign(secret)
            params["timestamp"] = timestamp
            params["sign"] = sign

        headers = {"Content-Type": "application/json"}

        if msgtype == "text":
            payload = {
                "msgtype": "text",
                "text": {"content": message},
            }
        else:
            payload = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title or "Keep Alert",
                    "text": message,
                },
            }

        if at_mobiles or at_userids or is_at_all:
            payload["at"] = {}
            if at_mobiles:
                payload["at"]["atMobiles"] = at_mobiles
            if at_userids:
                payload["at"]["atUserIds"] = at_userids
            if is_at_all:
                payload["at"]["isAtAll"] = is_at_all

        response = requests.post(
            "https://oapi.dingtalk.com/robot/send",
            params=params,
            headers=headers,
            json=payload,
            timeout=30,
        )

        if response.status_code == 200:
            result = response.json()
            if result.get("errcode") != 0:
                raise ProviderException(
                    f"{self.__class__.__name__} API error: {result.get('errcode')} - {result.get('errmsg')}"
                )
            return result
        elif response.status_code == 401:
            raise ProviderException(
                f"{self.__class__.__name__} unauthorized - invalid access token"
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
        title: str = None,
        msgtype: str = "text",
        at_mobiles: list = None,
        at_userids: list = None,
        is_at_all: bool = False,
        **kwargs: dict,
    ):
        """
        Notify alert message to DingTalk.

        Args:
            message (str): The message content to send.
            title (str): Title for markdown messages.
            msgtype (str): Message type ('text' or 'markdown').
            at_mobiles (list): List of mobile numbers to @mention.
            at_userids (list): List of user IDs to @mention.
            is_at_all (bool): Whether to @all members.
        """
        self.logger.debug("Notifying alert message to DingTalk")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(
            message=message,
            title=title,
            msgtype=msgtype,
            at_mobiles=at_mobiles,
            at_userids=at_userids,
            is_at_all=is_at_all,
        )

        self.logger.debug("Alert message notified to DingTalk")
        return {"message": message, "errcode": result.get("errcode"), "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    dingtalk_token = os.environ.get("DINGTALK_ACCESS_TOKEN")

    if dingtalk_token is None:
        raise Exception("DINGTALK_ACCESS_TOKEN is required")

    auth = {"access_token": dingtalk_token}
    dingtalk_secret = os.environ.get("DINGTALK_SECRET")
    if dingtalk_secret:
        auth["secret"] = dingtalk_secret

    config = ProviderConfig(
        description="DingTalk Output Provider",
        authentication=auth,
    )
    provider = DingTalkProvider(
        context_manager, provider_id="dingtalk-test", config=config
    )

    provider.notify(message="Hello from Keep!")
