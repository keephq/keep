"""
LINE Notify provider is an interface for LINE messaging notifications.
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
        },
        default="",
    )


class LineNotifyProvider(BaseProvider):
    """Send alert notifications via LINE Notify."""

    PROVIDER_DISPLAY_NAME = "LINE Notify"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["alert", "notification"]

    LINE_NOTIFY_API = "https://notify-api.line.me/api/notify"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = LineNotifyProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.access_token:
            raise ProviderException("LINE Notify access token is required")

    def dispose(self):
        pass

    def _notify(self, **kwargs) -> dict:
        """Send notification via LINE Notify API.

        LINE Notify API: POST https://notify-api.line.me/api/notify
        Form data: message (required), imageThumbnail, imageFullsize, imageFile, stickerPackageId, stickerId
        """
        message = kwargs.get("message", "")

        if not message:
            message = self._format_alert_message()

        # LINE Notify has 1000 char limit
        if len(message) > 1000:
            message = message[:997] + "..."

        headers = {
            "Authorization": f"Bearer {self.authentication_config.access_token}",
        }

        data = {"message": message}

        # Optional: sticker support
        if kwargs.get("sticker_package_id") and kwargs.get("sticker_id"):
            data["stickerPackageId"] = kwargs["sticker_package_id"]
            data["stickerId"] = kwargs["sticker_id"]

        response = requests.post(
            self.LINE_NOTIFY_API,
            headers=headers,
            data=data,
            timeout=30,
        )

        if response.status_code != 200:
            raise ProviderException(
                f"Failed to send LINE Notify: {response.status_code} {response.text}"
            )

        result = response.json()
        if result.get("status") != 200:
            raise ProviderException(
                f"LINE Notify API error: {result.get('status')} - {result.get('message', 'unknown')}"
            )

        return result

    def _format_alert_message(self) -> str:
        alert = self.context_manager.alert_data
        if not alert:
            return "Alert notification from Keep"
        name = alert.get("name", "Unknown Alert")
        severity = alert.get("severity", "unknown")
        description = alert.get("description", "No description")
        return f"[{severity.upper()}] {name}\n{description}"


if __name__ == "__main__":
    import os
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "access_token": os.environ.get("LINE_NOTIFY_TOKEN", ""),
        },
    )
    provider = LineNotifyProvider(
        context_manager=context_manager,
        provider_id="line-notify-test",
        config=config,
    )
    result = provider.notify(message="Test alert from Keep")
    print(f"Result: {result}")