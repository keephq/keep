"""
OpenSupports provider for Keep.

OpenSupports is an open-source, self-hosted ticketing and customer support
system with a REST API. This provider integrates Keep with OpenSupports to:

- Create tickets in OpenSupports when Keep alerts fire (notify/action)
- Pull open/pending tickets from OpenSupports as alert-like records

References:
- https://www.opensupports.com/
- https://www.opensupports.com/support/article/23/how-to-use-the-api/
- API endpoint pattern: POST /api/ticket/create, GET /api/ticket/get-all
"""

import dataclasses
import datetime

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class OpenSupportsProviderAuthConfig:
    """Authentication configuration for the OpenSupports provider."""

    host: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenSupports base URL",
            "hint": "https://support.example.com",
            "validation": "any_http_url",
            "sensitive": False,
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "OpenSupports staff API key",
            "hint": "Generated in OpenSupports → Staff → Edit → API Key",
            "sensitive": True,
        }
    )
    staff_email: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Staff account email address used to authenticate API requests",
            "hint": "The email address of the staff account that owns the API key",
            "sensitive": False,
        }
    )
    department_id: str = dataclasses.field(
        default="1",
        metadata={
            "required": False,
            "description": "Default department ID for new tickets",
            "hint": "Find department IDs in OpenSupports → Admin → Departments",
            "sensitive": False,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
    )


class OpenSupportsProvider(BaseProvider, ProviderHealthMixin):
    """Create and retrieve tickets in OpenSupports from Keep."""

    PROVIDER_DISPLAY_NAME = "OpenSupports"
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_CATEGORY = ["Ticketing"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="Authenticated with OpenSupports API",
            mandatory=True,
            alias="Authenticated",
        ),
        ProviderScope(
            name="create_ticket",
            description="Can create tickets in OpenSupports",
            mandatory=True,
            alias="Create Ticket",
        ),
    ]

    # OpenSupports priority levels (0=low, 1=medium, 2=high)
    PRIORITY_MAP = {
        AlertSeverity.CRITICAL: 2,
        AlertSeverity.HIGH: 2,
        AlertSeverity.WARNING: 1,
        AlertSeverity.INFO: 0,
        AlertSeverity.LOW: 0,
    }

    # Reverse map: OpenSupports priority → Keep severity
    SEVERITY_MAP = {
        2: AlertSeverity.HIGH,
        1: AlertSeverity.WARNING,
        0: AlertSeverity.LOW,
    }

    # OpenSupports ticket status: 0=opened, 1=closed
    STATUS_MAP = {
        0: AlertStatus.FIRING,
        1: AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = OpenSupportsProviderAuthConfig(
            **self.config.authentication
        )

    @property
    def _base_url(self) -> str:
        return str(self.authentication_config.host).rstrip("/")

    def _get_headers(self) -> dict:
        """OpenSupports uses HTTP Basic auth with staff email + API key."""
        return {
            "Content-Type": "application/json",
        }

    def _get_auth(self):
        """Build requests auth tuple (email, api_key)."""
        return (
            self.authentication_config.staff_email,
            self.authentication_config.api_key,
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Verify we can reach the OpenSupports API and authenticate."""
        try:
            resp = requests.get(
                f"{self._base_url}/api/staff/get-all",
                headers=self._get_headers(),
                auth=self._get_auth(),
                verify=self.authentication_config.verify_ssl,
                timeout=10,
            )
            if resp.status_code == 200:
                return {"authenticated": True, "create_ticket": True}
            else:
                msg = f"HTTP {resp.status_code}: {resp.text[:200]}"
                return {"authenticated": msg, "create_ticket": msg}
        except Exception as e:
            msg = str(e)
            return {"authenticated": msg, "create_ticket": msg}

    def _notify(
        self,
        title: str,
        description: str = "",
        priority: int = None,
        department_id: str = None,
        author_name: str = "Keep",
        author_email: str = "keep@keep.dev",
        **kwargs,
    ) -> dict:
        """
        Create a ticket in OpenSupports.

        Args:
            title:        Ticket subject/title.
            description:  Ticket body content (alert details, runbook link, etc.).
            priority:     OpenSupports priority (0=low, 1=medium, 2=high).
                          Defaults to 1 (medium) if not supplied.
            department_id: Target department. Defaults to the configured default.
            author_name:  Name shown as the ticket author.
            author_email: Email shown as the ticket author (must be a valid address).

        Returns:
            The created ticket response JSON from OpenSupports.
        """
        if department_id is None:
            department_id = self.authentication_config.department_id
        if priority is None:
            priority = 1  # medium

        self.logger.info(
            "Creating OpenSupports ticket",
            extra={"title": title, "department_id": department_id, "priority": priority},
        )

        payload = {
            "title": title,
            "content": description,
            "departmentId": int(department_id),
            "priority": int(priority),
            "authorName": author_name,
            "authorEmail": author_email,
            "language": kwargs.get("language", "en"),
        }

        resp = requests.post(
            f"{self._base_url}/api/ticket/create",
            headers=self._get_headers(),
            auth=self._get_auth(),
            json=payload,
            verify=self.authentication_config.verify_ssl,
            timeout=15,
        )
        try:
            resp.raise_for_status()
        except requests.HTTPError as e:
            self.logger.error(
                "Failed to create OpenSupports ticket",
                extra={"status_code": resp.status_code, "body": resp.text},
            )
            raise Exception(f"OpenSupports ticket creation failed: {e}") from e

        self.logger.info(
            "OpenSupports ticket created",
            extra={"status_code": resp.status_code},
        )
        return resp.json()

    def _get_alerts(self) -> list[AlertDto]:
        """Pull open and pending tickets from OpenSupports as Keep alerts."""
        self.logger.info("Fetching tickets from OpenSupports")
        try:
            resp = requests.get(
                f"{self._base_url}/api/ticket/get-all",
                headers=self._get_headers(),
                auth=self._get_auth(),
                params={"closed": 0, "page": 1},
                verify=self.authentication_config.verify_ssl,
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            self.logger.error(
                "Error fetching OpenSupports tickets", extra={"error": str(e)}
            )
            raise

        tickets = data.get("data", {}).get("tickets", [])
        return [self._ticket_to_alert(t) for t in tickets]

    def _ticket_to_alert(self, ticket: dict) -> AlertDto:
        """Convert an OpenSupports ticket dict to an AlertDto."""
        ticket_id = str(ticket.get("ticketNumber") or ticket.get("id", ""))
        status_code = ticket.get("closed", 0)
        priority_code = ticket.get("priority", 1)

        return AlertDto(
            id=ticket_id,
            fingerprint=ticket_id,
            name=ticket.get("title", "OpenSupports Ticket"),
            description=ticket.get("content", ""),
            severity=OpenSupportsProvider.SEVERITY_MAP.get(
                int(priority_code), AlertSeverity.WARNING
            ),
            status=OpenSupportsProvider.STATUS_MAP.get(
                int(status_code), AlertStatus.FIRING
            ),
            source=["opensupports"],
            lastReceived=ticket.get("date")
            or datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            url=f"{self._base_url}/tickets/{ticket_id}",
            assignee=ticket.get("owner", {}).get("name") if ticket.get("owner") else None,
            department=ticket.get("department", {}).get("name")
            if ticket.get("department")
            else None,
            payload=ticket,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Parse an incoming OpenSupports webhook event (if webhooks are configured).
        OpenSupports does not natively send webhooks, but this method allows
        future compatibility or custom webhook bridge setups.
        """
        ticket_id = str(event.get("ticketNumber") or event.get("id", ""))
        status_code = event.get("closed", 0)
        priority_code = event.get("priority", 1)

        return AlertDto(
            id=ticket_id,
            fingerprint=ticket_id,
            name=event.get("title", "OpenSupports Ticket"),
            description=event.get("content", ""),
            severity=OpenSupportsProvider.SEVERITY_MAP.get(
                int(priority_code), AlertSeverity.WARNING
            ),
            status=OpenSupportsProvider.STATUS_MAP.get(
                int(status_code), AlertStatus.FIRING
            ),
            source=["opensupports"],
            lastReceived=event.get("date")
            or datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            payload=event,
        )

    def dispose(self):
        pass
