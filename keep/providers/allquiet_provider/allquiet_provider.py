"""
AllQuietProvider integrates Keep with AllQuiet, an on-call alerting and
incident management platform.  It pulls active and recent incidents from
the AllQuiet REST API so you can correlate them with alerts from other tools.
"""

import dataclasses
import datetime
from typing import List

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope

ALLQUIET_API_BASE = "https://api.allquiet.app/v1"


@pydantic.dataclasses.dataclass
class AllQuietProviderAuthConfig:
    """
    AllQuietProviderAuthConfig holds authentication configuration for AllQuiet.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "AllQuiet Team API key",
            "hint": "Generate under Settings > Team > API keys in AllQuiet",
            "sensitive": True,
        },
    )


class AllQuietProvider(BaseProvider):
    """Pull on-call incidents and alerts from AllQuiet into Keep."""

    PROVIDER_DISPLAY_NAME = "AllQuiet"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incidents:read",
            description="Read incidents from AllQuiet",
            mandatory=True,
            alias="Read Incidents",
            documentation_url="https://allquiet.app/api",
        ),
    ]

    # AllQuiet severity → Keep severity
    _SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
        "minor": AlertSeverity.LOW,
        "major": AlertSeverity.HIGH,
    }

    # AllQuiet status → Keep status
    _STATUS_MAP = {
        "open": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
        "closed": AlertStatus.RESOLVED,
        "silenced": AlertStatus.SUPPRESSED,
        "pending": AlertStatus.PENDING,
    }

    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = AllQuietProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes by hitting the incidents endpoint."""
        scopes: dict[str, bool | str] = {}
        try:
            resp = requests.get(
                f"{ALLQUIET_API_BASE}/incidents",
                headers=self._get_headers(),
                params={"limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                scopes["incidents:read"] = True
            elif resp.status_code == 401:
                scopes["incidents:read"] = "Unauthorized — check your API key"
            elif resp.status_code == 403:
                scopes["incidents:read"] = "Forbidden — insufficient permissions"
            else:
                scopes["incidents:read"] = f"Unexpected response: {resp.status_code}"
        except Exception as e:
            self.logger.exception("Failed to validate AllQuiet scopes")
            scopes["incidents:read"] = str(e)
        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """Pull active and recent incidents from AllQuiet."""
        self.logger.info("Fetching incidents from AllQuiet")
        alerts: List[AlertDto] = []
        page = 1
        page_size = 100

        while True:
            try:
                resp = requests.get(
                    f"{ALLQUIET_API_BASE}/incidents",
                    headers=self._get_headers(),
                    params={
                        "page": page,
                        "limit": page_size,
                        "status": "open,acknowledged",  # only active
                    },
                    timeout=15,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                self.logger.error("Error fetching AllQuiet incidents (page %d): %s", page, e)
                break

            data = resp.json()
            incidents = data if isinstance(data, list) else data.get("incidents", data.get("data", []))

            if not isinstance(incidents, list) or not incidents:
                break

            for incident in incidents:
                alert = self._incident_to_alert(incident)
                if alert:
                    alerts.append(alert)

            # Pagination: stop if we got fewer than page_size
            if len(incidents) < page_size:
                break
            page += 1

        self.logger.info("Fetched %d AllQuiet alerts", len(alerts))
        return alerts

    def _incident_to_alert(self, incident: dict) -> "AlertDto | None":
        """Map an AllQuiet incident dict to a Keep AlertDto."""
        try:
            incident_id = str(incident.get("id", ""))
            title = incident.get("title") or incident.get("name") or f"Incident #{incident_id}"
            severity_raw = incident.get("severity", incident.get("priority", "warning")).lower()
            status_raw = incident.get("status", "open").lower()

            created_at = incident.get("created_at") or incident.get("createdAt") or incident.get("timestamp")
            updated_at = incident.get("updated_at") or incident.get("updatedAt") or created_at

            if updated_at:
                try:
                    last_received = datetime.datetime.fromisoformat(
                        str(updated_at).replace("Z", "+00:00")
                    )
                except (ValueError, AttributeError):
                    last_received = datetime.datetime.utcnow()
            else:
                last_received = datetime.datetime.utcnow()

            assignee = ""
            if incident.get("assignee"):
                assignee = incident["assignee"].get("name") or incident["assignee"].get("email", "")

            url = incident.get("url") or incident.get("permalink") or f"https://app.allquiet.app/incidents/{incident_id}"

            return AlertDto(
                id=incident_id,
                name=title,
                severity=self._SEVERITY_MAP.get(severity_raw, AlertSeverity.WARNING),
                status=self._STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                lastReceived=last_received,
                description=incident.get("description") or incident.get("summary") or title,
                source=["allquiet"],
                url=url,
                fingerprint=incident_id,
                assignee=assignee,
                labels=incident.get("labels", incident.get("tags", [])),
                service=incident.get("service") or incident.get("team") or "",
                environment=incident.get("environment", ""),
            )
        except Exception as e:
            self.logger.error("Failed to map AllQuiet incident to AlertDto: %s", e)
            return None

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format an AllQuiet webhook payload into an AlertDto."""
        severity_raw = event.get("severity", event.get("priority", "warning")).lower()
        status_raw = event.get("status", "open").lower()

        severity = AllQuietProvider._SEVERITY_MAP.get(severity_raw, AlertSeverity.WARNING)
        status = AllQuietProvider._STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        ts = event.get("created_at") or event.get("timestamp")
        if ts:
            try:
                last_received = datetime.datetime.fromisoformat(
                    str(ts).replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow()
        else:
            last_received = datetime.datetime.utcnow()

        incident_id = str(event.get("id", ""))
        return AlertDto(
            id=incident_id,
            name=event.get("title") or event.get("name") or f"AllQuiet Incident #{incident_id}",
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=event.get("description") or event.get("summary") or "",
            source=["allquiet"],
            url=event.get("url") or f"https://app.allquiet.app/incidents/{incident_id}",
            fingerprint=incident_id,
            service=event.get("service") or event.get("team") or "",
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_key = os.environ.get("ALLQUIET_API_KEY")
    if not api_key:
        raise EnvironmentError("ALLQUIET_API_KEY must be set")

    config = ProviderConfig(
        description="AllQuiet Provider",
        authentication={"api_key": api_key},
    )
    provider = AllQuietProvider(
        context_manager, provider_id="allquiet-test", config=config
    )
    print(provider.validate_scopes())
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} alerts")
    for a in alerts:
        print(f"  - {a.name}: {a.severity} ({a.status})")
