"""
xMattersProvider integrates Keep with xMatters on-call management and alerting platform.
Supports pulling active events from the xMatters REST API and receiving real-time
inbound webhook/integration payloads from xMatters flows.
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
class XmattersProviderAuthConfig:
    """
    XmattersProviderAuthConfig holds connection details for xMatters.
    """

    base_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "xMatters instance URL (e.g. https://company.xmatters.com)",
            "sensitive": False,
            "hint": "Your xMatters base URL, e.g. https://acme.xmatters.com",
        },
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "xMatters API key (from xMatters → Developer → API Keys)",
            "sensitive": True,
        },
    )


class XmattersProvider(BaseProvider):
    """Pull active events from xMatters and receive inbound webhook payloads."""

    PROVIDER_DISPLAY_NAME = "xMatters"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_events",
            description="Read events from xMatters API",
            mandatory=True,
        ),
    ]

    # xMatters event status → Keep AlertStatus
    STATUS_MAP = {
        "ACTIVE": AlertStatus.FIRING,
        "SUSPENDED": AlertStatus.ACKNOWLEDGED,
        "TERMINATED": AlertStatus.RESOLVED,
        "TERMINATED_EXTERNAL": AlertStatus.RESOLVED,
        "active": AlertStatus.FIRING,
        "suspended": AlertStatus.ACKNOWLEDGED,
        "terminated": AlertStatus.RESOLVED,
    }

    # xMatters event priority → Keep AlertSeverity
    SEVERITY_MAP = {
        "HIGH": AlertSeverity.HIGH,
        "MEDIUM": AlertSeverity.WARNING,
        "LOW": AlertSeverity.LOW,
        "high": AlertSeverity.HIGH,
        "medium": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
    }

    webhook_documentation_here_differs_from_general_documentation = True
    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send xMatters alerts to Keep, configure an outbound integration (HTTP Trigger) in xMatters:

1. In xMatters, navigate to **Flows** and open (or create) the flow for your monitoring integration.
2. Add an **HTTP Trigger** step to the flow canvas.
3. In the HTTP Trigger configuration, set:
   - **URL**: `{keep_webhook_api_url}`
   - **Method**: POST
   - **Authentication**: Custom Headers
   - Add header: `X-API-KEY` = `{api_key}`
4. Map the relevant event fields (name, priority, status, etc.) to the HTTP Trigger payload.
5. Save and activate the flow.

Alternatively, use an **Outbound Integration** (webhook) from the xMatters integration builder:
- Trigger type: **Event Status Updated**
- Target URL: `{keep_webhook_api_url}`
- Header: `X-API-KEY: {api_key}`
"""

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = XmattersProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    def _base_url(self) -> str:
        return self.authentication_config.base_url.rstrip("/")

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                f"{self._base_url()}/api/xm/1/events",
                headers=self._get_headers(),
                params={"limit": 1, "status": "ACTIVE"},
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_events": True}
            return {
                "read_events": f"HTTP {response.status_code}: {response.text[:200]}"
            }
        except Exception as e:
            self.logger.error("Error validating xMatters scopes: %s", e)
            return {"read_events": str(e)}

    def _get_alerts(self) -> List[AlertDto]:
        alerts = []
        try:
            self.logger.info("Pulling active events from xMatters")
            offset = 0
            limit = 100

            while True:
                response = requests.get(
                    f"{self._base_url()}/api/xm/1/events",
                    headers=self._get_headers(),
                    params={
                        "status": "ACTIVE",
                        "limit": limit,
                        "offset": offset,
                    },
                    timeout=30,
                )
                if not response.ok:
                    self.logger.error(
                        "Failed to fetch xMatters events: %s", response.text
                    )
                    break

                data = response.json()
                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    alerts.append(self._item_to_alert_dto(item))

                total = data.get("total", 0)
                offset += limit
                if offset >= total:
                    break

        except Exception as e:
            self.logger.error("Error pulling xMatters events: %s", e)
        return alerts

    def _item_to_alert_dto(self, item: dict) -> AlertDto:
        event_id = item.get("id", "")
        event_type = item.get("eventType", "")
        priority = item.get("priority", "MEDIUM")
        status = item.get("status", "ACTIVE")
        created_at = item.get("created")
        terminated_at = item.get("terminated")
        last_received = terminated_at or created_at or datetime.datetime.utcnow().isoformat()

        # Form name / description from eventType or properties
        name = event_type or f"xMatters Event {event_id}"
        properties = item.get("properties", {})
        description = properties.get("description", properties.get("summary", ""))

        return AlertDto(
            id=event_id,
            name=name,
            description=description,
            severity=self.SEVERITY_MAP.get(priority, AlertSeverity.WARNING),
            status=self.STATUS_MAP.get(status, AlertStatus.FIRING),
            lastReceived=last_received,
            startedAt=created_at,
            url=f"{self._base_url()}/ui/events?id={event_id}",
            source=["xmatters"],
            labels={
                "priority": priority,
                "eventType": event_type,
                "planName": item.get("plan", {}).get("name", ""),
                "formName": item.get("form", {}).get("name", ""),
            },
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format an xMatters outbound webhook payload into an AlertDto.

        xMatters sends payloads from Flow Designer HTTP Trigger steps.
        The exact shape depends on how the flow is configured, but common fields
        include: id, eventType, priority, status, created, properties.
        """
        event_id = event.get("id", event.get("eventId", ""))
        priority = event.get("priority", event.get("Priority", "MEDIUM"))
        status = event.get("status", event.get("Status", "ACTIVE"))
        created_at = event.get("created", event.get("Created"))
        terminated_at = event.get("terminated", event.get("Terminated"))
        last_received = terminated_at or created_at or datetime.datetime.utcnow().isoformat()

        name = (
            event.get("eventType")
            or event.get("name")
            or event.get("subject")
            or f"xMatters Event {event_id}"
        )
        description = event.get("description", event.get("summary", ""))

        return AlertDto(
            id=str(event_id),
            name=name,
            description=description,
            severity=XmattersProvider.SEVERITY_MAP.get(priority, AlertSeverity.WARNING),
            status=XmattersProvider.STATUS_MAP.get(status, AlertStatus.FIRING),
            lastReceived=last_received,
            startedAt=created_at,
            url=event.get("url", ""),
            source=["xmatters"],
            labels={
                "priority": priority,
                "eventType": event.get("eventType", ""),
                "planName": event.get("planName", ""),
                "formName": event.get("formName", ""),
            },
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    base_url = os.environ.get("XMATTERS_URL", "https://company.xmatters.com")
    api_key = os.environ.get("XMATTERS_API_KEY", "")

    if not api_key:
        raise Exception("XMATTERS_API_KEY is not set")

    config = ProviderConfig(
        description="xMatters Provider",
        authentication={"base_url": base_url, "api_key": api_key},
    )

    provider = XmattersProvider(
        context_manager,
        provider_id="xmatters-test",
        config=config,
    )

    events = provider._get_alerts()
    print(f"Found {len(events)} active events")
    for e in events:
        print(e)
