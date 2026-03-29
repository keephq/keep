"""
OpenSupportsProvider — Keep integration for OpenSupports (https://www.opensupports.com/).

OpenSupports is an open-source, self-hosted customer support ticketing system.
This provider supports:

  - **Pull mode**: fetch open tickets as AlertDtos
  - **Push (webhook) mode**: receive ticket events via HTTP webhooks
  - **notify()**: create a new support ticket programmatically
  - **_query()**: search/list existing tickets
  - **validate_scopes()**: verify API token + server connectivity

Authentication: API token (`Authorization: Token <token>` header).
REST API base: `<server_url>/api/`

Docs: https://www.opensupports.com/docs/api
"""

import dataclasses
import datetime
import typing

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod


# ---------------------------------------------------------------------------
# Authentication config
# ---------------------------------------------------------------------------


@pydantic.dataclasses.dataclass
class OpenSupportsProviderAuthConfig:
    """Authentication configuration for the OpenSupports provider."""

    server_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Base URL of your OpenSupports instance",
            "hint": "https://support.yourcompany.com",
            "validation": "any_http_url",
        }
    )

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenSupports API token (Staff token with ticket permissions)",
            "hint": "Obtain from Administration → Staff → API Token",
            "sensitive": True,
        }
    )

    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify TLS/SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "type": "switch",
        },
    )


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class OpenSupportsProvider(BaseProvider):
    """Integrate OpenSupports ticketing system with Keep."""

    PROVIDER_DISPLAY_NAME = "OpenSupports"
    PROVIDER_CATEGORY = ["Ticketing", "Customer Support"]
    PROVIDER_TAGS = ["ticketing", "itsm"]

    # ------------------------------------------------------------------
    # Webhook support — OpenSupports can call a webhook on ticket events
    # ------------------------------------------------------------------
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To receive ticket events from OpenSupports in Keep:

1. Log in to OpenSupports as an administrator.
2. Go to **Administration → System Settings → Webhooks**.
3. Add a new webhook:
   - **URL**: `{keep_webhook_api_url}`
   - **Events**: *New Ticket*, *Ticket Replied*, *Ticket Closed*
   - **Secret Header**: `x-api-key: {api_key}`
4. Save the configuration.

Keep will receive ticket events in real-time as alerts.
"""

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity",
            description="Validate API token and server connectivity.",
            mandatory=True,
            alias="Connectivity",
        ),
        ProviderScope(
            name="tickets:read",
            description="Read / list support tickets.",
            mandatory=False,
            alias="Read Tickets",
        ),
        ProviderScope(
            name="tickets:write",
            description="Create and update support tickets.",
            mandatory=False,
            alias="Write Tickets",
        ),
    ]

    # Severity mapping — OpenSupports uses Priority 1–4
    # 1 = Low, 2 = Medium, 3 = High, 4 = Critical
    PRIORITY_SEVERITY_MAP: dict[int, AlertSeverity] = {
        1: AlertSeverity.LOW,
        2: AlertSeverity.WARNING,
        3: AlertSeverity.HIGH,
        4: AlertSeverity.CRITICAL,
    }
    # String priority labels (API v3+ may return strings)
    PRIORITY_STR_MAP: dict[str, AlertSeverity] = {
        "low": AlertSeverity.LOW,
        "medium": AlertSeverity.WARNING,
        "high": AlertSeverity.HIGH,
        "critical": AlertSeverity.CRITICAL,
    }

    STATUS_MAP: dict[str, AlertStatus] = {
        "open": AlertStatus.FIRING,
        "pending": AlertStatus.FIRING,
        "waiting": AlertStatus.FIRING,
        "closed": AlertStatus.RESOLVED,
        "resolved": AlertStatus.RESOLVED,
    }

    FINGERPRINT_FIELDS = ["id", "ticketNumber"]

    PROVIDER_METHODS = [
        ProviderMethod(
            name="Create Ticket",
            func_name="create_ticket",
            description="Create a new support ticket in OpenSupports",
            type="action",
            scopes=["tickets:write"],
            arguments=[
                {
                    "name": "title",
                    "description": "Ticket title / subject",
                    "required": True,
                    "type": "str",
                },
                {
                    "name": "content",
                    "description": "Ticket body / description",
                    "required": True,
                    "type": "str",
                },
                {
                    "name": "department_id",
                    "description": "Department ID to assign the ticket to",
                    "required": False,
                    "type": "int",
                },
                {
                    "name": "priority",
                    "description": "Ticket priority: 1 (low), 2 (medium), 3 (high), 4 (critical)",
                    "required": False,
                    "type": "int",
                },
                {
                    "name": "email",
                    "description": "Customer email for the ticket (required if no auth user)",
                    "required": False,
                    "type": "str",
                },
                {
                    "name": "name",
                    "description": "Customer name for the ticket",
                    "required": False,
                    "type": "str",
                },
            ],
        ),
        ProviderMethod(
            name="Close Ticket",
            func_name="close_ticket",
            description="Close an existing OpenSupports ticket",
            type="action",
            scopes=["tickets:write"],
            arguments=[
                {
                    "name": "ticket_number",
                    "description": "Ticket number to close",
                    "required": True,
                    "type": "str",
                },
            ],
        ),
        ProviderMethod(
            name="Add Reply",
            func_name="add_reply",
            description="Add a reply to an existing ticket",
            type="action",
            scopes=["tickets:write"],
            arguments=[
                {
                    "name": "ticket_number",
                    "description": "Ticket number",
                    "required": True,
                    "type": "str",
                },
                {
                    "name": "content",
                    "description": "Reply content",
                    "required": True,
                    "type": "str",
                },
            ],
        ),
    ]

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ) -> None:
        super().__init__(context_manager, provider_id, config)

    # ------------------------------------------------------------------
    # BaseProvider overrides
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        self.authentication_config = OpenSupportsProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self) -> None:
        pass

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _base_url(self) -> str:
        return str(self.authentication_config.server_url).rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Token {self.authentication_config.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _get(self, path: str, params: typing.Optional[dict] = None) -> dict:
        url = f"{self._base_url()}/api/{path.lstrip('/')}"
        try:
            resp = requests.get(
                url,
                headers=self._headers(),
                params=params,
                verify=self.authentication_config.verify_ssl,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json()
        except requests.HTTPError as exc:
            raise ProviderException(
                f"OpenSupports API error {exc.response.status_code} on GET {path}: "
                f"{exc.response.text[:300]}"
            ) from exc
        except requests.RequestException as exc:
            raise ProviderException(
                f"OpenSupports request failed on GET {path}: {exc}"
            ) from exc

    def _post(self, path: str, data: dict) -> dict:
        url = f"{self._base_url()}/api/{path.lstrip('/')}"
        try:
            resp = requests.post(
                url,
                headers=self._headers(),
                json=data,
                verify=self.authentication_config.verify_ssl,
                timeout=15,
            )
            resp.raise_for_status()
            return resp.json() if resp.text.strip() else {}
        except requests.HTTPError as exc:
            raise ProviderException(
                f"OpenSupports API error {exc.response.status_code} on POST {path}: "
                f"{exc.response.text[:300]}"
            ) from exc
        except requests.RequestException as exc:
            raise ProviderException(
                f"OpenSupports request failed on POST {path}: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Scope validation
    # ------------------------------------------------------------------

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes: dict[str, bool | str] = {}

        # connectivity check via GET /api/staff/get-all-tickets?page=1
        try:
            self._get("staff/get-all-tickets", {"page": 1, "perPage": 1})
            scopes["connectivity"] = True
            scopes["tickets:read"] = True
        except ProviderException as exc:
            scopes["connectivity"] = str(exc)
            scopes["tickets:read"] = str(exc)

        # write check — try to validate a known endpoint exists
        # (we don't create a real ticket, just verify the endpoint is accessible)
        try:
            # HEAD-style: if we can GET the department list, write is likely allowed
            self._get("department/list")
            scopes["tickets:write"] = True
        except ProviderException as exc:
            scopes["tickets:write"] = str(exc)

        return scopes

    # ------------------------------------------------------------------
    # Pull mode — fetch open tickets as AlertDtos
    # ------------------------------------------------------------------

    def _get_alerts(self) -> list[AlertDto]:
        """Fetch open/pending tickets from OpenSupports via REST API."""
        alerts: list[AlertDto] = []
        page = 1
        while True:
            try:
                data = self._get(
                    "staff/get-all-tickets",
                    {"page": page, "perPage": 50, "status": "open"},
                )
            except ProviderException as exc:
                self.logger.warning("OpenSupports pull page %d failed: %s", page, exc)
                break

            tickets = data.get("data", {}).get("tickets", data.get("tickets", []))
            if not isinstance(tickets, list) or not tickets:
                break

            for ticket in tickets:
                alert = self._ticket_to_alert_dto(ticket)
                if alert:
                    alerts.append(alert)

            # Pagination: stop when we get fewer than perPage results
            if len(tickets) < 50:
                break
            page += 1

        return alerts

    # ------------------------------------------------------------------
    # Push (webhook) mode
    # ------------------------------------------------------------------

    @staticmethod
    def _format_alert(
        event: dict | list, provider_instance: "OpenSupportsProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """Convert an OpenSupports webhook payload to AlertDto(s)."""
        if isinstance(event, list):
            results = []
            for item in event:
                dto = OpenSupportsProvider._ticket_to_alert_dto(item)
                if dto:
                    results.append(dto)
            return results if results else []

        # Top-level may have a 'ticket' or 'data' key
        ticket = event.get("ticket") or event.get("data") or event
        dto = OpenSupportsProvider._ticket_to_alert_dto(ticket)
        return dto if dto else AlertDto(name="OpenSupports Event", source=["opensupports"])

    # ------------------------------------------------------------------
    # Ticket → AlertDto conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _ticket_to_alert_dto(ticket: dict) -> typing.Optional[AlertDto]:
        if not isinstance(ticket, dict):
            return None

        ticket_id = str(ticket.get("ticketNumber") or ticket.get("id") or "")
        title = ticket.get("title") or ticket.get("subject") or "OpenSupports Ticket"
        content = ticket.get("content") or ticket.get("description") or ""
        raw_status = str(ticket.get("status", "open")).lower()
        status = OpenSupportsProvider.STATUS_MAP.get(raw_status, AlertStatus.FIRING)

        # Priority → severity
        raw_priority = ticket.get("priority")
        if isinstance(raw_priority, int):
            severity = OpenSupportsProvider.PRIORITY_SEVERITY_MAP.get(
                raw_priority, AlertSeverity.INFO
            )
        elif isinstance(raw_priority, str):
            severity = OpenSupportsProvider.PRIORITY_STR_MAP.get(
                raw_priority.lower(), AlertSeverity.INFO
            )
        else:
            severity = AlertSeverity.INFO

        # Timestamp
        last_received: typing.Optional[datetime.datetime] = None
        for ts_field in ("date", "createdAt", "updatedAt", "lastModification"):
            ts_raw = ticket.get(ts_field)
            if ts_raw:
                try:
                    if isinstance(ts_raw, (int, float)):
                        last_received = datetime.datetime.utcfromtimestamp(float(ts_raw))
                    elif isinstance(ts_raw, str):
                        last_received = datetime.datetime.fromisoformat(
                            ts_raw.replace("Z", "+00:00")
                        )
                    break
                except (ValueError, OSError, OverflowError):
                    continue

        # Department
        dept = ticket.get("department") or {}
        dept_name = dept.get("name") if isinstance(dept, dict) else str(dept)

        # Owner / author
        owner = ticket.get("owner") or ticket.get("author") or {}
        author_name = (
            owner.get("name")
            if isinstance(owner, dict)
            else str(owner) if owner else None
        )

        labels: dict[str, str] = {}
        if dept_name:
            labels["department"] = str(dept_name)
        if author_name:
            labels["author"] = str(author_name)
        if raw_priority is not None:
            labels["priority"] = str(raw_priority)

        return AlertDto(
            id=ticket_id or None,
            name=str(title),
            description=str(content) if content else None,
            severity=severity,
            status=status,
            lastReceived=last_received.isoformat() if last_received else None,
            startedAt=last_received.isoformat() if last_received else None,
            source=["opensupports"],
            ticketUrl=(
                f"{ticket.get('url', '')}" if ticket.get("url") else None
            ),
            labels=labels,
            ticketNumber=ticket_id or None,
        )

    # ------------------------------------------------------------------
    # Action methods
    # ------------------------------------------------------------------

    def create_ticket(
        self,
        title: str,
        content: str,
        department_id: typing.Optional[int] = None,
        priority: typing.Optional[int] = None,
        email: typing.Optional[str] = None,
        name: typing.Optional[str] = None,
    ) -> dict:
        """Create a new support ticket in OpenSupports."""
        payload: dict = {"title": title, "content": content}
        if department_id is not None:
            payload["departmentId"] = department_id
        if priority is not None:
            payload["priority"] = priority
        if email:
            payload["email"] = email
        if name:
            payload["name"] = name

        result = self._post("user/create-ticket", payload)
        self.logger.info(
            "Created OpenSupports ticket: %s",
            result.get("data", {}).get("ticketNumber", "?"),
        )
        return result

    def close_ticket(self, ticket_number: str) -> dict:
        """Close an existing ticket by its ticket number."""
        result = self._post(
            "staff/close-ticket", {"ticketNumber": ticket_number}
        )
        self.logger.info("Closed OpenSupports ticket #%s", ticket_number)
        return result

    def add_reply(self, ticket_number: str, content: str) -> dict:
        """Add a reply/comment to an existing ticket."""
        result = self._post(
            "staff/add-comment",
            {"ticketNumber": ticket_number, "content": content},
        )
        self.logger.info("Added reply to OpenSupports ticket #%s", ticket_number)
        return result

    def _notify(
        self,
        title: str = "",
        message: str = "",
        severity: str = "medium",
        department_id: typing.Optional[int] = None,
        ticket_number: typing.Optional[str] = None,
        **kwargs,
    ) -> dict:
        """Keep notify() interface — create a support ticket.

        Maps Keep severity strings to OpenSupports priority integers:
          critical → 4, high → 3, medium/warning → 2, low/info → 1
        """
        priority_map = {
            "critical": 4,
            "high": 3,
            "warning": 2,
            "medium": 2,
            "low": 1,
            "info": 1,
        }
        priority = priority_map.get(severity.lower(), 2)
        return self.create_ticket(
            title=title or kwargs.get("summary", "Keep Alert"),
            content=message or kwargs.get("description", ""),
            department_id=department_id,
            priority=priority,
        )

    def _query(
        self,
        status: str = "open",
        page: int = 1,
        per_page: int = 25,
        **kwargs,
    ) -> list[dict]:
        """Query support tickets by status."""
        data = self._get(
            "staff/get-all-tickets",
            {"page": page, "perPage": per_page, "status": status},
        )
        return data.get("data", {}).get("tickets", data.get("tickets", []))


# ---------------------------------------------------------------------------
# Manual test entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import logging
    import os

    from keep.providers.providers_factory import ProvidersFactory

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(tenant_id="singletenant", workflow_id="test")

    config = {
        "authentication": {
            "server_url": os.environ["OPENSUPPORTS_URL"],
            "api_token": os.environ["OPENSUPPORTS_TOKEN"],
        }
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="opensupports-test",
        provider_type="opensupports",
        provider_config=config,
    )
    print("Scopes:", provider.validate_scopes())
    alerts = provider.get_alerts()
    print(f"Fetched {len(alerts)} tickets as alerts")
    for a in alerts[:5]:
        print(" -", a.name, a.severity, a.status)
