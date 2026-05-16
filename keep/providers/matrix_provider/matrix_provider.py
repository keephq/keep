"""
Matrix (Element) provider is an interface for Matrix room notifications.
"""

import dataclasses
import json

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class MatrixProviderAuthConfig:
    """Matrix authentication configuration."""

    homeserver_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix homeserver URL (e.g. https://matrix.org)",
        },
        default="",
    )
    access_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix bot access token",
            "sensitive": True,
        },
        default="",
    )
    room_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Matrix room ID (e.g. !abc123:matrix.org)",
        },
        default="",
    )


class MatrixProvider(BaseProvider):
    """Send alert notifications to Matrix rooms via bot."""

    PROVIDER_DISPLAY_NAME = "Matrix"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["alert", "notification"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MatrixProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.homeserver_url:
            raise ProviderException("Matrix homeserver URL is required")
        if not self.authentication_config.access_token:
            raise ProviderException("Matrix access token is required")
        if not self.authentication_config.room_id:
            raise ProviderException("Matrix room ID is required")

    def dispose(self):
        pass

    def _notify(self, **kwargs) -> dict:
        """Send notification to Matrix room."""
        message = kwargs.get("message", "")
        message_type = kwargs.get("message_type", "m.text")

        if not message:
            message = self._format_alert_message()

        # Matrix client-server API: PUT /_matrix/client/v3/rooms/{roomId}/send/m.room.message/{txnId}
        import uuid
        txn_id = str(uuid.uuid4())

        url = (
            f"{self.authentication_config.homeserver_url.rstrip('/')}"
            f"/_matrix/client/v3/rooms/{self.authentication_config.room_id}"
            f"/send/m.room.message/{txn_id}"
        )

        payload = {
            "msgtype": message_type,
            "body": message,
        }

        # If markdown, use org.matrix.custom.html format
        if kwargs.get("format") == "html":
            payload["format"] = "org.matrix.custom.html"
            payload["formatted_body"] = kwargs.get("html", message)

        headers = {
            "Authorization": f"Bearer {self.authentication_config.access_token}",
            "Content-Type": "application/json",
        }

        response = requests.put(
            url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code not in (200, 201):
            raise ProviderException(
                f"Failed to send Matrix notification: {response.status_code} {response.text}"
            )

        return response.json()

    def _format_alert_message(self) -> str:
        alert = self.context_manager.alert_data
        if not alert:
            return "Alert notification from Keep"
        name = alert.get("name", "Unknown Alert")
        severity = alert.get("severity", "unknown")
        description = alert.get("description", "No description")
        return f"[{severity.upper()}] {name}: {description}"


if __name__ == "__main__":
    import os
    context_manager = ContextManager(tenant_id="test", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "homeserver_url": os.environ.get("MATRIX_HOMESERVER", "https://matrix.org"),
            "access_token": os.environ.get("MATRIX_ACCESS_TOKEN", ""),
            "room_id": os.environ.get("MATRIX_ROOM_ID", ""),
        },
    )
    provider = MatrixProvider(
        context_manager=context_manager,
        provider_id="matrix-test",
        config=config,
    )
    result = provider.notify(message="Test alert", title="Keep Alert")
    print(f"Result: {result}")