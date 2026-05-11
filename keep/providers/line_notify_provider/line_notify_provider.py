"""
LINE Notify Provider is a class that implements the BaseOutputProvider interface for LINE Notify messages.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class LineNotifyProviderAuthConfig:
    """LINE Notify authentication configuration."""

    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "LINE Notify Access Token",
            "sensitive": True,
            "config_main_group": "authentication",
        }
    )


class LineNotifyProvider(BaseProvider):
    """Send alert message to LINE Notify."""

    PROVIDER_DISPLAY_NAME = "LINE Notify"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["messaging"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LineNotifyProviderAuthConfig(
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
            self._send_message("Keep test message", notification_disabled=True)
            return {"send_message": True}
        except Exception as e:
            return {"send_message": str(e)}

    def _send_message(
        self,
        message: str,
        image_thumbnail: str = None,
        image_fullsize: str = None,
        sticker_package_id: str = None,
        sticker_id: str = None,
        notification_disabled: bool = False,
    ):
        """
        Send a message to LINE Notify.
        https://notify-bot.line.me/doc/en/
        """
        access_token = self.authentication_config.access_token

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required"
            )

        headers = {
            "Authorization": f"Bearer {access_token}",
        }

        payload = {"message": message}

        if image_thumbnail:
            payload["imageThumbnail"] = image_thumbnail
        if image_fullsize:
            payload["imageFullsize"] = image_fullsize
        if sticker_package_id:
            payload["stickerPackageId"] = sticker_package_id
        if sticker_id:
            payload["stickerId"] = sticker_id
        if notification_disabled:
            payload["notificationDisabled"] = "true"

        response = requests.post(
            "https://notify-api.line.me/api/notify",
            headers=headers,
            data=payload,
            timeout=30,
        )

        if response.status_code == 200:
            return response.json()
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
        image_thumbnail: str = None,
        image_fullsize: str = None,
        sticker_package_id: str = None,
        sticker_id: str = None,
        notification_disabled: bool = False,
        **kwargs: dict,
    ):
        """
        Notify alert message to LINE Notify.

        Args:
            message (str): The message to send (max 1000 characters).
            image_thumbnail (str): URL of thumbnail image (max 240x240px).
            image_fullsize (str): URL of full-size image (max 2048x2048px).
            sticker_package_id (str): Sticker package ID.
            sticker_id (str): Sticker ID.
            notification_disabled (bool): If True, the user will not receive a push notification.
        """
        self.logger.debug("Notifying alert message to LINE Notify")

        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} message is required to trigger notification"
            )

        result = self._send_message(
            message=message,
            image_thumbnail=image_thumbnail,
            image_fullsize=image_fullsize,
            sticker_package_id=sticker_package_id,
            sticker_id=sticker_id,
            notification_disabled=notification_disabled,
        )

        self.logger.debug("Alert message notified to LINE Notify")
        return {"message": message, "status": result.get("status"), "sent": True}


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    line_notify_token = os.environ.get("LINE_NOTIFY_TOKEN")

    if line_notify_token is None:
        raise Exception("LINE_NOTIFY_TOKEN is required")

    config = ProviderConfig(
        description="LINE Notify Output Provider",
        authentication={"access_token": line_notify_token},
    )
    provider = LineNotifyProvider(
        context_manager, provider_id="line-notify-test", config=config
    )

    provider.notify(message="Hello from Keep!")
