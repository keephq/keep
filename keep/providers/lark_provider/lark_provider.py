"""
LarkProvider integrates with Lark (Feishu) Service Desk and messaging platform,
allowing Keep to receive webhook events from Lark/Feishu service desk tickets and
send notifications via Lark Bot messages.
"""

import dataclasses
import datetime
import hashlib
import hmac
import time
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class LarkProviderAuthConfig:
    """
    LarkProviderAuthConfig holds authentication configuration for the Lark provider.
    """

    app_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Lark / Feishu App ID",
            "hint": "Found in the Lark Open Platform developer console at https://open.feishu.cn/app",
            "sensitive": False,
        },
    )

    app_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Lark / Feishu App Secret",
            "hint": "Found in the Lark Open Platform developer console alongside the App ID",
            "sensitive": True,
        },
    )

    webhook_token: Optional[str] = dataclasses.field(
        default=None,
        metadata={
            "required": False,
            "description": "Verification token for incoming Lark event webhooks",
            "hint": "Found in the Lark Open Platform > Event Subscriptions page for your app",
            "sensitive": True,
        },
    )

    base_url: str = dataclasses.field(
        default="https://open.feishu.cn",
        metadata={
            "required": False,
            "description": "Lark/Feishu API base URL",
            "hint": "Use https://open.feishu.cn for Feishu (China) or https://open.larksuite.com for Lark (International)",
            "sensitive": False,
        },
    )


class LarkProvider(BaseProvider):
    """Receive Lark/Feishu service desk ticket events and send Lark bot notifications."""

    PROVIDER_DISPLAY_NAME = "Lark / Feishu"
    PROVIDER_CATEGORY = ["Ticketing", "Collaboration"]
    PROVIDER_TAGS = ["alert", "ticketing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="Successfully authenticated with the Lark Open Platform",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    # Lark service desk ticket status → Keep AlertStatus
    STATUS_MAP = {
        "1": AlertStatus.FIRING,    # Open
        "2": AlertStatus.FIRING,    # Pending
        "3": AlertStatus.RESOLVED,  # Resolved
        "4": AlertStatus.RESOLVED,  # Closed
    }

    # Lark ticket urgency → Keep AlertSeverity
    URGENCY_MAP = {
        "1": AlertSeverity.CRITICAL,   # P1 / Critical
        "2": AlertSeverity.HIGH,       # P2 / High
        "3": AlertSeverity.WARNING,    # P3 / Medium
        "4": AlertSeverity.INFO,       # P4 / Low
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = LarkProviderAuthConfig(
            **self.config.authentication
        )

    def __get_access_token(self) -> str:
        """Fetch or return a cached tenant access token."""
        now = time.time()
        if self._access_token and now < self._token_expiry - 60:
            return self._access_token

        url = f"{self.authentication_config.base_url}/open-apis/auth/v3/tenant_access_token/internal"
        payload = {
            "app_id": self.authentication_config.app_id,
            "app_secret": self.authentication_config.app_secret,
        }
        response = requests.post(url, json=payload, timeout=15)
        response.raise_for_status()
        data = response.json()

        if data.get("code") != 0:
            raise ValueError(
                f"Lark auth failed: {data.get('msg', 'unknown error')}"
            )

        self._access_token = data["tenant_access_token"]
        self._token_expiry = now + data.get("expire", 7200)
        return self._access_token

    def __get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.__get_access_token()}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate credentials by obtaining a tenant access token."""
        try:
            token = self.__get_access_token()
            if token:
                return {"authenticated": True}
            return {"authenticated": "Could not obtain access token"}
        except requests.exceptions.HTTPError as e:
            return {"authenticated": f"HTTP error: {e.response.status_code} {e.response.text}"}
        except ValueError as e:
            return {"authenticated": str(e)}
        except Exception as e:
            self.logger.error("Error validating Lark scopes: %s", e)
            return {"authenticated": f"Error: {e}"}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull open service desk tickets from Lark.
        Requires the helpdesk.ticket:readonly scope on the app.
        """
        alerts = []
        base = self.authentication_config.base_url
        url = f"{base}/open-apis/helpdesk/v1/tickets"
        params = {"status": "1,2", "page_size": 50}  # Open and pending tickets

        try:
            self.logger.info("Fetching open Lark service desk tickets")
            while True:
                response = requests.get(
                    url,
                    headers=self.__get_headers(),
                    params=params,
                    timeout=15,
                )
                response.raise_for_status()
                data = response.json()

                if data.get("code") != 0:
                    self.logger.error("Lark API error: %s", data.get("msg"))
                    break

                ticket_list = data.get("data", {}).get("ticket_list", [])
                for ticket in ticket_list:
                    alerts.append(self.__ticket_to_alert(ticket))

                page_token = data.get("data", {}).get("next_page_token")
                if not page_token:
                    break
                params["page_token"] = page_token

        except Exception as e:
            self.logger.error("Error fetching Lark service desk tickets: %s", e)

        return alerts

    def __ticket_to_alert(self, ticket: dict) -> AlertDto:
        """Convert a Lark service desk ticket to an AlertDto."""
        ticket_id = ticket.get("ticket_id", "unknown")
        title = ticket.get("name", f"Ticket {ticket_id}")
        description = ticket.get("description", "")
        status_code = str(ticket.get("status", "1"))
        urgency = str(ticket.get("urgency", "3"))

        status = self.STATUS_MAP.get(status_code, AlertStatus.FIRING)
        severity = self.URGENCY_MAP.get(urgency, AlertSeverity.WARNING)

        created_at = ticket.get("created_at")
        last_received = (
            datetime.datetime.fromtimestamp(int(created_at), tz=datetime.timezone.utc).isoformat()
            if created_at
            else datetime.datetime.utcnow().isoformat()
        )

        agent = ticket.get("agent_service_status", {})
        assignee = ticket.get("agent_user_id", "")

        base = self.authentication_config.base_url.replace("open.", "")
        ticket_url = f"{base}/helpdesk/tickets/{ticket_id}"

        return AlertDto(
            id=f"lark-ticket-{ticket_id}",
            name=title,
            description=description,
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["lark"],
            url=ticket_url,
            labels={
                "ticket_id": ticket_id,
                "urgency": urgency,
                "status_code": status_code,
                "assignee": str(assignee),
            },
            fingerprint=f"lark-ticket-{ticket_id}",
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Lark webhook event payload into an AlertDto.

        Lark delivers events in a wrapper envelope:
        {
          "schema": "2.0",
          "header": { "event_type": "helpdesk.ticket.created_v1", ... },
          "event": { "ticket": { ... } }
        }
        """
        header = event.get("header", {})
        event_type = header.get("event_type", "unknown")
        inner_event = event.get("event", {})

        # Handle both ticket and message events
        if "ticket" in event_type:
            ticket = inner_event.get("ticket", inner_event)
            ticket_id = ticket.get("ticket_id", header.get("event_id", "unknown"))
            title = ticket.get("name", f"Ticket {ticket_id}")
            description = ticket.get("description", "")
            status_code = str(ticket.get("status", "1"))
            urgency = str(ticket.get("urgency", "3"))

            status_map = {
                "1": AlertStatus.FIRING,
                "2": AlertStatus.FIRING,
                "3": AlertStatus.RESOLVED,
                "4": AlertStatus.RESOLVED,
            }
            urgency_map = {
                "1": AlertSeverity.CRITICAL,
                "2": AlertSeverity.HIGH,
                "3": AlertSeverity.WARNING,
                "4": AlertSeverity.INFO,
            }

            status = status_map.get(status_code, AlertStatus.FIRING)
            severity = urgency_map.get(urgency, AlertSeverity.WARNING)

            created_at = ticket.get("created_at")
            last_received = (
                datetime.datetime.fromtimestamp(int(created_at), tz=datetime.timezone.utc).isoformat()
                if created_at
                else datetime.datetime.utcnow().isoformat()
            )

            return AlertDto(
                id=f"lark-ticket-{ticket_id}",
                name=title,
                description=description,
                severity=severity,
                status=status,
                lastReceived=last_received,
                source=["lark"],
                labels={
                    "ticket_id": ticket_id,
                    "event_type": event_type,
                    "urgency": urgency,
                    "status_code": status_code,
                },
                fingerprint=f"lark-ticket-{ticket_id}",
            )

        # Generic Lark message/notification event
        event_id = header.get("event_id", "unknown")
        create_time = header.get("create_time", "")
        last_received = datetime.datetime.utcnow().isoformat()
        if create_time:
            try:
                ts_ms = int(create_time)
                last_received = datetime.datetime.fromtimestamp(
                    ts_ms / 1000, tz=datetime.timezone.utc
                ).isoformat()
            except (ValueError, TypeError):
                pass

        message = inner_event.get("message", {})
        content = message.get("content", str(inner_event))

        return AlertDto(
            id=f"lark-event-{event_id}",
            name=f"Lark event: {event_type}",
            description=content[:500] if isinstance(content, str) else str(content)[:500],
            severity=AlertSeverity.INFO,
            status=AlertStatus.FIRING,
            lastReceived=last_received,
            source=["lark"],
            labels={
                "event_id": event_id,
                "event_type": event_type,
            },
            fingerprint=f"lark-event-{event_id}",
        )
