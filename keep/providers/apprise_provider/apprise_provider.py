"""
AppriseProvider - send alerts to 70+ notification services via self-hosted Apprise API.
"""

import dataclasses
from typing import Optional

import pydantic
import requests

from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class AppriseProviderAuthConfig:
    """Authentication configuration for AppriseProvider."""

    server_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Apprise API server URL (e.g. http://apprise:8000)",
            "sensitive": False,
            "hint": "http://localhost:8000",
        }
    )

    tag: str = dataclasses.field(
        default="all",
        metadata={
            "required": False,
            "description": "Apprise tag/group to notify (default: all)",
            "sensitive": False,
        },
    )

    api_key: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Apprise API key (if authentication is enabled)",
            "sensitive": True,
        },
    )


class AppriseProvider(BaseProvider):
    """Send alerts to 70+ notification services via self-hosted Apprise API."""

    PROVIDER_DISPLAY_NAME = "Apprise"
    PROVIDER_CATEGORY = ["Collaboration"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="notify",
            mandatory=True,
            alias="Send Notification",
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = AppriseProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        return {"notify": True}

    def dispose(self):
        pass

    def _notify(
        self,
        message: str = "",
        title: str = "Keep Alert",
        notification_type: str = "info",
        **kwargs,
    ):
        """
        Send a notification via Apprise API.

        Args:
            message: The notification body (required).
            title: The notification title (default: "Keep Alert").
            notification_type: Apprise type — info, success, warning, or failure (default: info).
        """
        if not message:
            raise ProviderException(
                f"{self.__class__.__name__} requires a message"
            )

        base = self.authentication_config.server_url.rstrip("/")
        tag = self.authentication_config.tag
        url = f"{base}/notify/{tag}"

        headers = {"Content-Type": "application/json"}
        if self.authentication_config.api_key:
            headers["Authorization"] = f"Bearer {self.authentication_config.api_key}"

        payload = {"title": title, "body": message, "type": notification_type}

        self.logger.debug(f"Sending Apprise notification to {url}")
        response = requests.post(url, json=payload, headers=headers, timeout=30)

        if response.status_code not in (200, 204):
            raise ProviderException(
                f"{self.__class__.__name__} failed: HTTP {response.status_code} - {response.text}"
            )

        self.logger.debug("Apprise notification sent successfully")
        return {"status": "ok", "url": url}


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    apprise_server_url = os.environ.get("APPRISE_SERVER_URL", "http://localhost:8000")
    apprise_tag = os.environ.get("APPRISE_TAG", "all")
    apprise_api_key = os.environ.get("APPRISE_API_KEY")

    config = ProviderConfig(
        description="Apprise Provider",
        authentication={
            "server_url": apprise_server_url,
            "tag": apprise_tag,
            "api_key": apprise_api_key,
        },
    )

    provider = AppriseProvider(
        context_manager,
        provider_id="apprise-test",
        config=config,
    )

    provider.notify(
        message="Test alert from Keep via Apprise",
        title="Keep Test",
        notification_type="info",
    )
