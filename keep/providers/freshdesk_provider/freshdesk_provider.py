"""
FreshdeskProvider integrates with Freshdesk customer support platform,
allowing Keep to pull tickets as alerts and receive webhook notifications
for new and updated tickets.
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
class FreshdeskProviderAuthConfig:
    """
    FreshdeskProviderAuthConfig holds authentication configuration for Freshdesk.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Freshdesk API Key",
            "hint": "Found at https://<your-domain>.freshdesk.com/profile/settings under 'Your API Key'",
            "sensitive": True,
        },
    )
    domain: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Freshdesk domain (e.g. 'yourcompany' from yourcompany.freshdesk.com)",
            "hint": "The subdomain part of your Freshdesk URL",
        },
    )


class FreshdeskProvider(BaseProvider):
    """Pull support tickets from Freshdesk and receive webhook notifications."""

    PROVIDER_DISPLAY_NAME = "Freshdesk"
    PROVIDER_CATEGORY = ["Ticketing"]
    PROVIDER_TAGS = ["ticketing", "alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with Freshdesk API",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    # Freshdesk ticket status codes
    STATUS_MAP = {
        2: AlertStatus.FIRING,    # Open
        3: AlertStatus.FIRING,    # Pending
        4: AlertStatus.RESOLVED,  # Resolved
        5: AlertStatus.RESOLVED,  # Closed
    }

    # Freshdesk priority codes
    PRIORITY_MAP = {
        1: AlertSeverity.LOW,      # Low
        2: AlertSeverity.INFO,     # Medium
        3: AlertSeverity.HIGH,     # High
        4: AlertSeverity.CRITICAL, # Urgent
    }

    PRIORITY_NAMES = {1: "Low", 2: "Medium", 3: "High", 4: "Urgent"}
    STATUS_NAMES = {2: "Open", 3: "Pending", 4: "Resolved", 5: "Closed"}

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = FreshdeskProviderAuthConfig(
            **self.config.authentication
        )

    def __get_base_url(self) -> str:
        return f"https://{self.authentication_config.domain}.freshdesk.com/api/v2"

    def __get_auth(self):
        # Freshdesk uses HTTP Basic Auth with the API key as username and 'X' as password
        return (self.authentication_config.api_key, "X")

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate API key by fetching agent details."""
        try:
            response = requests.get(
                f"{self.__get_base_url()}/agents/me",
                auth=self.__get_auth(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"authenticated": True}
            elif response.status_code == 401:
                return {"authenticated": "Invalid API key or domain"}
            elif response.status_code == 403:
                return {"authenticated": "Access denied — check API key permissions"}
            else:
                return {
                    "authenticated": f"Unexpected status: {response.status_code}"
                }
        except Exception as e:
            self.logger.error("Error validating Freshdesk scopes: %s", e)
            return {"authenticated": f"Error connecting to Freshdesk: {e}"}

    def _get_alerts(self) -> List[AlertDto]:
        """Pull open and pending tickets from Freshdesk."""
        alerts = []
        try:
            self.logger.info(
                "Fetching tickets from Freshdesk domain: %s",
                self.authentication_config.domain,
            )
            page = 1
            while True:
                response = requests.get(
                    f"{self.__get_base_url()}/tickets",
                    auth=self.__get_auth(),
                    params={
                        "per_page": 100,
                        "page": page,
                        "order_by": "updated_at",
                        "order_type": "desc",
                    },
                    timeout=30,
                )

                if not response.ok:
                    self.logger.error(
                        "Failed to fetch Freshdesk tickets: %s", response.text
                    )
                    break

                tickets = response.json()
                if not tickets:
                    break

                for ticket in tickets:
                    alerts.append(self.__ticket_to_alert(ticket))

                # Freshdesk returns up to 100 per page; if less than 100, we're done
                if len(tickets) < 100:
                    break
                page += 1

        except Exception as e:
            self.logger.error("Error fetching Freshdesk tickets: %s", e)

        return alerts

    def __ticket_to_alert(self, ticket: dict) -> AlertDto:
        """Convert a Freshdesk ticket to an AlertDto."""
        ticket_id = str(ticket.get("id", "unknown"))
        subject = ticket.get("subject", "No subject")
        status_code = ticket.get("status", 2)
        priority_code = ticket.get("priority", 2)
        description_text = ticket.get("description_text", ticket.get("description", ""))
        requester_email = ticket.get("requester_id", "")
        updated_at = ticket.get("updated_at", ticket.get("created_at", ""))
        tags = ticket.get("tags", [])

        status = self.STATUS_MAP.get(status_code, AlertStatus.FIRING)
        severity = self.PRIORITY_MAP.get(priority_code, AlertSeverity.INFO)

        if updated_at:
            try:
                last_received = datetime.datetime.fromisoformat(
                    updated_at.replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow().isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        url = f"https://{self.authentication_config.domain}.freshdesk.com/helpdesk/tickets/{ticket_id}"

        return AlertDto(
            id=ticket_id,
            name=subject,
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=description_text[:500] if description_text else "",
            source=["freshdesk"],
            url=url,
            labels={
                "ticket_id": ticket_id,
                "status": self.STATUS_NAMES.get(status_code, str(status_code)),
                "priority": self.PRIORITY_NAMES.get(priority_code, str(priority_code)),
                "tags": ",".join(tags) if tags else "",
                "type": ticket.get("type", ""),
            },
            fingerprint=ticket_id,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a Freshdesk webhook payload into an AlertDto."""
        freshdesk_data = event.get("freshdesk_webhook", event)
        ticket_id = str(freshdesk_data.get("ticket_id", event.get("id", "unknown")))
        subject = freshdesk_data.get("ticket_subject", "No subject")
        status_str = freshdesk_data.get("ticket_status", "Open").lower()
        priority_str = freshdesk_data.get("ticket_priority", "Medium").lower()

        # Map string status to AlertStatus
        status_map = {
            "open": AlertStatus.FIRING,
            "pending": AlertStatus.FIRING,
            "resolved": AlertStatus.RESOLVED,
            "closed": AlertStatus.RESOLVED,
        }
        status = status_map.get(status_str, AlertStatus.FIRING)

        # Map string priority to severity
        priority_map = {
            "low": AlertSeverity.LOW,
            "medium": AlertSeverity.INFO,
            "high": AlertSeverity.HIGH,
            "urgent": AlertSeverity.CRITICAL,
        }
        severity = priority_map.get(priority_str, AlertSeverity.INFO)

        url = freshdesk_data.get("ticket_url", "")
        description = freshdesk_data.get("ticket_description", "")

        return AlertDto(
            id=ticket_id,
            name=subject,
            severity=severity,
            status=status,
            lastReceived=datetime.datetime.utcnow().isoformat(),
            description=description[:500] if description else "",
            source=["freshdesk"],
            url=url,
            labels={
                "ticket_id": ticket_id,
                "status": freshdesk_data.get("ticket_status", ""),
                "priority": freshdesk_data.get("ticket_priority", ""),
                "requester": freshdesk_data.get("ticket_requester_name", ""),
                "assignee": freshdesk_data.get("ticket_assignee_name", ""),
            },
            fingerprint=ticket_id,
        )
