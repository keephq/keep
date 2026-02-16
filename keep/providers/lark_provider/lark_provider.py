"""
LarkProvider is a class that allows to ingest/digest data from Lark/Feishu helpdesk.
"""

import dataclasses
import time
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.models.provider_scope import ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class LarkProviderAuthConfig:
    """
    Lark/Feishu authentication configuration.
    """

    app_id: str = dataclasses.field(
        metadata={
            "required": True,
            "sensitive": False,
            "description": "Lark App ID",
        }
    )
    app_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "sensitive": True,
            "description": "Lark App Secret",
        }
    )
    helpdesk_id: Optional[str] = dataclasses.field(
        metadata={
            "required": False,
            "sensitive": False,
            "description": "Lark Helpdesk ID",
        },
        default=None,
    )


class LarkProvider(BaseProvider):
    """Receive alerts from Lark/Feishu helpdesk and manage tickets."""

    LARK_API_BASE = "https://open.larksuite.com"

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
    To send helpdesk ticket events from Lark/Feishu to Keep:

    1. Go to the [Lark Open Platform](https://open.larksuite.com/) and open your app.
    2. Navigate to **Event Subscriptions** in the left sidebar.
    3. Set the **Request URL** to: `{keep_webhook_api_url}`
    4. Add the following events:
       - `helpdesk.ticket.created_v1`
       - `helpdesk.ticket.updated_v1`
    5. Under **Security Settings**, add `X-API-KEY` with value `{api_key}` as a custom header (or use the verification token).
    6. Save and publish the app version.
    7. Helpdesk ticket events will now be forwarded to Keep.
    """

    PROVIDER_DISPLAY_NAME = "Lark/Feishu"
    PROVIDER_CATEGORY = ["Ticketing"]
    PROVIDER_TAGS = ["ticketing"]
    FINGERPRINT_FIELDS = ["ticket_id"]

    # Lark tokens expire after 2 hours; refresh after 110 minutes to be safe
    _TOKEN_TTL_SECONDS = 110 * 60

    PROVIDER_SCOPES = [
        ProviderScope(
            name="helpdesk:ticket:read",
            description="Read helpdesk tickets.",
            mandatory=True,
            alias="Helpdesk Ticket Read",
        ),
        ProviderScope(
            name="helpdesk:ticket:write",
            description="Create helpdesk tickets.",
            mandatory=False,
            alias="Helpdesk Ticket Write",
        ),
    ]

    # Map Lark ticket priority (1=urgent … 4=low) to Keep severity
    PRIORITY_SEVERITY_MAP = {
        1: AlertSeverity.CRITICAL,
        2: AlertSeverity.HIGH,
        3: AlertSeverity.WARNING,
        4: AlertSeverity.LOW,
        "urgent": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "medium": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._tenant_access_token = None
        self._token_obtained_at = 0

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Lark provider.
        """
        self.authentication_config = LarkProviderAuthConfig(
            **self.config.authentication
        )

    def _get_tenant_access_token(self) -> str:
        """
        Obtain a tenant_access_token from Lark Open API.
        Tokens are cached and refreshed before expiry (~2h TTL).
        """
        if (
            self._tenant_access_token
            and (time.time() - self._token_obtained_at) < self._TOKEN_TTL_SECONDS
        ):
            return self._tenant_access_token

        response = requests.post(
            f"{self.LARK_API_BASE}/open-apis/auth/v3/tenant_access_token/internal",
            json={
                "app_id": self.authentication_config.app_id,
                "app_secret": self.authentication_config.app_secret,
            },
        )
        response.raise_for_status()
        data = response.json()
        if data.get("code") != 0:
            raise Exception(f"Failed to get tenant access token: {data.get('msg')}")
        self._tenant_access_token = data["tenant_access_token"]
        self._token_obtained_at = time.time()
        return self._tenant_access_token

    def _get_auth_headers(self) -> dict:
        token = self._get_tenant_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _query(self, **kwargs: dict):
        """
        Query Lark helpdesk tickets.

        Returns:
            list: List of helpdesk tickets.
        """
        headers = self._get_auth_headers()
        helpdesk_id = kwargs.get("helpdesk_id") or self.authentication_config.helpdesk_id

        params = {}
        if helpdesk_id:
            params["helpdesk_id"] = helpdesk_id

        response = requests.get(
            f"{self.LARK_API_BASE}/open-apis/helpdesk/v1/tickets",
            headers=headers,
            params=params,
        )
        response.raise_for_status()
        return response.json()

    def _notify(self, summary: str = "", description: str = "", **kwargs: dict):
        """
        Create a helpdesk ticket in Lark.
        """
        headers = self._get_auth_headers()

        body = {
            "summary": summary or kwargs.get("title", "Keep Alert"),
            "description": description or kwargs.get("message", ""),
        }
        if self.authentication_config.helpdesk_id:
            body["helpdesk_id"] = self.authentication_config.helpdesk_id

        response = requests.post(
            f"{self.LARK_API_BASE}/open-apis/helpdesk/v1/tickets",
            headers=headers,
            json=body,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Lark helpdesk ticket event into an AlertDto.
        """
        # Lark event subscriptions wrap data in header + event
        header = event.get("header", {})
        event_data = event.get("event", event)
        event_type = header.get("event_type", event.get("type", ""))

        ticket = event_data.get("ticket", event_data)
        ticket_id = ticket.get("ticket_id", ticket.get("id", ""))
        summary = ticket.get("summary", ticket.get("title", "Lark Ticket"))
        description = ticket.get("description", "")
        status_name = ticket.get("status", {}).get("name", "") if isinstance(ticket.get("status"), dict) else str(ticket.get("status", ""))
        created_at = ticket.get("created_at", "")
        updated_at = ticket.get("updated_at", "")
        helpdesk_id = ticket.get("helpdesk_id", "")

        # Map ticket status to alert status
        status_lower = status_name.lower()
        if status_lower in ("resolved", "closed"):
            alert_status = AlertStatus.RESOLVED
        else:
            alert_status = AlertStatus.FIRING

        # Map ticket priority to severity
        priority = ticket.get("priority", ticket.get("ticket_type", {}).get("priority"))
        if isinstance(priority, str):
            priority = priority.lower()
        severity = LarkProvider.PRIORITY_SEVERITY_MAP.get(priority, AlertSeverity.INFO)

        alert = AlertDto(
            id=f"lark-{ticket_id}" if ticket_id else "lark-unknown",
            name=summary,
            description=description,
            severity=severity,
            status=alert_status,
            source=["lark"],
            ticket_id=ticket_id,
            helpdesk_id=helpdesk_id,
            event_type=event_type,
            lastReceived=updated_at or created_at,
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    import os

    app_id = os.environ.get("LARK_APP_ID")
    app_secret = os.environ.get("LARK_APP_SECRET")

    config = {
        "authentication": {"app_id": app_id, "app_secret": app_secret},
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="lark_test",
        provider_type="lark",
        provider_config=config,
    )
    result = provider.query()
    print(result)
