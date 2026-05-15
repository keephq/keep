"""
Gotify provider is an interface for Gotify push notifications.
"""

import dataclasses
import requests

import pydantic

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class GotifyProviderAuthConfig:
    """Gotify authentication configuration."""

    url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify Server URL (e.g. https://gotify.example.com)",
        },
        default="",
    )
    token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Gotify Application Token",
            "sensitive": True,
        },
        default="",
    )


class GotifyProvider(BaseProvider):
    """Send push notifications via self-hosted Gotify server."""

    PROVIDER_DISPLAY_NAME = "Gotify"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["alert", "notification", "self-hosted"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = GotifyProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.url:
            raise ProviderException("Gotify server URL is required")
        if not self.authentication_config.token:
            raise ProviderException("Gotify application token is required")

    def dispose(self):
        pass

    def _notify(self, **kwargs) -> dict:
        """Send push notification to Gotify server.

        Gotify API: POST /message?token=<token>
        Body: {"title": "...", "message": "...", "priority": 5}
        """
        title = kwargs.get("title", "Keep Alert")
        message = kwargs.get("message", "")
        priority = kwargs.get("priority", 5)

        if not message:
            message = self._format_alert_message()

        # Build Gotify API URL
        url = f"{self.authentication_config.url.rstrip('/')}/message"
        
        # Severity to priority mapping
        alert = self.context_manager.alert_data
        if alert:
            severity = alert.get("severity", "info")
            priority_map = {
                "critical": 10,
                "high": 8,
                "warning": 5,
                "info": 3,
                "low": 1,
            }
            priority = priority_map.get(severity.lower(), 5)

        payload = {
            "title": title,
            "message": message,
            "priority": priority,
        }

        response = requests.post(
            url,
            json=payload,
            params={"token": self.authentication_config.token},
            timeout=30,
        )

        if response.status_code != 200:
            raise ProviderException(
                f"Failed to send Gotify notification: {response.status_code} {response.text}"
            )

        return response.json()

    def _format_alert_message(self) -> str:
        """Format alert data into a readable message."""
        alert = self.context_manager.alert_data
        if not alert:
            return "Alert notification from Keep"

        name = alert.get("name", "Unknown Alert")
        severity = alert.get("severity", "unknown")
        description = alert.get("description", "No description")
        return f"[{severity.upper()}] {name}: {description}"
