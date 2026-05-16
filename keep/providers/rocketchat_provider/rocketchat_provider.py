"""
Rocket.Chat provider is an interface for Rocket.Chat bot notifications.
"""

import dataclasses

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class RocketchatProviderAuthConfig:
    """Rocket.Chat authentication configuration."""

    webhook_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rocket.Chat Incoming Webhook URL",
            "sensitive": True,
        },
        default="",
    )
    token: str = dataclasses.field(
        metadata={
            "description": "Rocket.Chat Personal Access Token (optional)",
            "required": False,
            "sensitive": True,
        },
        default="",
    )


class RocketchatProvider(BaseProvider):
    """Send alert notifications to Rocket.Chat channels via incoming webhook."""

    PROVIDER_DISPLAY_NAME = "Rocket.Chat"
    PROVIDER_CATEGORY = ["Collaboration"]
    PROVIDER_TAGS = ["alert", "notification"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = RocketchatProviderAuthConfig(
            **self.config.authentication
        )
        if not self.authentication_config.webhook_url:
            raise ProviderException("Rocket.Chat webhook URL is required")

    def dispose(self):
        pass

    def _notify(self, **kwargs) -> dict:
        """Send notification to Rocket.Chat channel via webhook."""
        message = kwargs.get("message", "")
        title = kwargs.get("title", "Keep Alert")

        if not message:
            message = self._format_alert_message()

        payload = {
            "text": f"**{title}**\n{message}",
        }

        headers = {"Content-Type": "application/json"}
        if self.authentication_config.token:
            headers["X-Auth-Token"] = self.authentication_config.token

        response = requests.post(
            self.authentication_config.webhook_url,
            json=payload,
            headers=headers,
            timeout=30,
        )

        if response.status_code not in (200, 201):
            raise ProviderException(
                f"Failed to send Rocket.Chat notification: {response.status_code} {response.text}"
            )

        return {"status": "sent", "status_code": response.status_code}

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
            "webhook_url": os.environ.get("ROCKETCHAT_WEBHOOK_URL", ""),
        },
    )
    provider = RocketchatProvider(
        context_manager=context_manager,
        provider_id="rocketchat-test",
        config=config,
    )
    result = provider.notify(message="Test alert", title="Keep Alert")
    print(f"Result: {result}")