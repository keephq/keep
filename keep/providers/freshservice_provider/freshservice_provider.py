"""
FreshserviceProvider is a class that provides integration with Freshservice ITSM.
It supports pulling tickets/incidents as alerts and creating tickets via API.
"""

import dataclasses
import datetime
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class FreshserviceProviderAuthConfig:
    """
    FreshserviceProviderAuthConfig holds authentication credentials for Freshservice.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Freshservice API Key",
            "sensitive": True,
        },
    )

    domain: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Freshservice domain (e.g. yourcompany.freshservice.com)",
            "sensitive": False,
            "hint": "yourcompany.freshservice.com",
        },
    )


class FreshserviceProvider(BaseProvider):
    """Pull alerts (tickets/incidents) from Freshservice and create tickets."""

    PROVIDER_DISPLAY_NAME = "Freshservice"
    PROVIDER_TAGS = ["ticketing"]
    PROVIDER_CATEGORY = ["ITSM"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_tickets",
            description="Read tickets and incidents from Freshservice",
            mandatory=True,
        ),
    ]

    # Freshservice ticket priority → Keep severity
    PRIORITY_MAP = {
        1: AlertSeverity.LOW,       # Low
        2: AlertSeverity.INFO,      # Medium
        3: AlertSeverity.HIGH,      # High
        4: AlertSeverity.CRITICAL,  # Urgent
    }

    # Freshservice ticket status → Keep alert status
    STATUS_MAP = {
        1: AlertStatus.FIRING,      # Open
        2: AlertStatus.FIRING,      # Pending
        3: AlertStatus.RESOLVED,    # Resolved
        4: AlertStatus.RESOLVED,    # Closed
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = FreshserviceProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _get_base_url(self) -> str:
        domain = self.authentication_config.domain.rstrip("/")
        if not domain.startswith("http"):
            domain = f"https://{domain}"
        return f"{domain}/api/v2"

    def _get_headers(self) -> dict:
        import base64
        credentials = base64.b64encode(
            f"{self.authentication_config.api_key}:X".encode()
        ).decode()
        return {
            "Authorization": f"Basic {credentials}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                f"{self._get_base_url()}/tickets?per_page=1",
                headers=self._get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_tickets": True}
            else:
                return {
                    "read_tickets": f"HTTP {response.status_code}: {response.text[:200]}"
                }
        except Exception as e:
            self.logger.error("Error validating Freshservice scopes: %s", e)
            return {"read_tickets": str(e)}

    def _get_alerts(self) -> List[AlertDto]:
        """Pull open tickets from Freshservice as alerts."""
        alerts = []
        page = 1
        per_page = 100

        try:
            while True:
                response = requests.get(
                    f"{self._get_base_url()}/tickets",
                    headers=self._get_headers(),
                    params={
                        "per_page": per_page,
                        "page": page,
                        "order_by": "updated_at",
                        "order_type": "desc",
                    },
                    timeout=30,
                )
                response.raise_for_status()
                data = response.json()
                tickets = data.get("tickets", [])

                if not tickets:
                    break

                for ticket in tickets:
                    alert = self._ticket_to_alert(ticket)
                    alerts.append(alert)

                if len(tickets) < per_page:
                    break
                page += 1

        except Exception as e:
            self.logger.error("Error fetching tickets from Freshservice: %s", e)
            raise

        self.logger.info("Fetched %d tickets from Freshservice", len(alerts))
        return alerts

    def _ticket_to_alert(self, ticket: dict) -> AlertDto:
        priority = ticket.get("priority", 2)
        status_code = ticket.get("status", 1)
        severity = self.PRIORITY_MAP.get(priority, AlertSeverity.INFO)
        status = self.STATUS_MAP.get(status_code, AlertStatus.FIRING)

        updated_at = ticket.get("updated_at") or ticket.get("created_at")
        try:
            last_received = datetime.datetime.fromisoformat(
                updated_at.replace("Z", "+00:00")
            ).isoformat()
        except Exception:
            last_received = datetime.datetime.utcnow().isoformat()

        return AlertDto(
            id=str(ticket["id"]),
            name=ticket.get("subject", f"Ticket #{ticket['id']}"),
            description=ticket.get("description_text", ""),
            severity=severity,
            status=status,
            lastReceived=last_received,
            source=["freshservice"],
            ticket_id=ticket.get("id"),
            requester_id=ticket.get("requester_id"),
            responder_id=ticket.get("responder_id"),
            group_id=ticket.get("group_id"),
            ticket_type=ticket.get("type", "Incident"),
            tags=ticket.get("tags", []),
            due_by=ticket.get("due_by"),
            url=f"https://{self.authentication_config.domain}/helpdesk/tickets/{ticket['id']}",
        )

    def _notify(
        self,
        subject: str,
        description: str,
        priority: int = 2,
        email: Optional[str] = None,
        **kwargs,
    ) -> dict:
        """
        Create a new ticket in Freshservice.

        Args:
            subject: Ticket subject/title
            description: Ticket description
            priority: 1=Low, 2=Medium, 3=High, 4=Urgent
            email: Requester email address
        """
        payload = {
            "subject": subject,
            "description": description,
            "priority": priority,
            "status": 2,  # Open
        }
        if email:
            payload["email"] = email

        response = requests.post(
            f"{self._get_base_url()}/tickets",
            headers=self._get_headers(),
            json=payload,
            timeout=30,
        )
        response.raise_for_status()
        ticket = response.json().get("ticket", {})
        self.logger.info("Created Freshservice ticket #%s", ticket.get("id"))
        return ticket

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Handle incoming Freshservice webhook payloads."""
        freshdesk_event = event.get("freshdesk_webhook", event)
        ticket_id = freshdesk_event.get("ticket_id", freshdesk_event.get("id"))
        priority_label = (freshdesk_event.get("ticket_priority") or "").lower()
        status_label = (freshdesk_event.get("ticket_status") or "").lower()

        priority_name_map = {
            "low": AlertSeverity.LOW,
            "medium": AlertSeverity.INFO,
            "high": AlertSeverity.HIGH,
            "urgent": AlertSeverity.CRITICAL,
        }
        status_name_map = {
            "open": AlertStatus.FIRING,
            "pending": AlertStatus.FIRING,
            "resolved": AlertStatus.RESOLVED,
            "closed": AlertStatus.RESOLVED,
        }

        severity = priority_name_map.get(priority_label, AlertSeverity.INFO)
        status = status_name_map.get(status_label, AlertStatus.FIRING)

        return AlertDto(
            id=str(ticket_id) if ticket_id else None,
            name=freshdesk_event.get(
                "ticket_subject", freshdesk_event.get("subject", "Freshservice Ticket")
            ),
            description=freshdesk_event.get("ticket_description", ""),
            severity=severity,
            status=status,
            lastReceived=datetime.datetime.utcnow().isoformat(),
            source=["freshservice"],
            ticket_id=ticket_id,
            url=freshdesk_event.get("ticket_url", ""),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("FRESHSERVICE_API_KEY")
    domain = os.environ.get("FRESHSERVICE_DOMAIN")

    if not api_key:
        raise Exception("FRESHSERVICE_API_KEY is required")
    if not domain:
        raise Exception("FRESHSERVICE_DOMAIN is required")

    config = ProviderConfig(
        description="Freshservice Provider",
        authentication={
            "api_key": api_key,
            "domain": domain,
        },
    )

    provider = FreshserviceProvider(
        context_manager=context_manager,
        provider_id="freshservice",
        config=config,
    )

    scopes = provider.validate_scopes()
    print("Scopes:", scopes)

    alerts = provider.get_alerts()
    print(f"Got {len(alerts)} alerts")
    for alert in alerts[:3]:
        print(alert)
