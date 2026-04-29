"""
BigPandaProvider integrates Keep with BigPanda, an AIOps platform that uses
machine learning to correlate alerts, reduce noise, and surface actionable
incidents from monitoring tool noise.
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

BIGPANDA_API_BASE = "https://api.bigpanda.io/resources/v2.0"


@pydantic.dataclasses.dataclass
class BigPandaProviderAuthConfig:
    """
    Authentication configuration for BigPanda.
    """

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "BigPanda API bearer token",
            "hint": "Generate under Settings > API Integrations in BigPanda",
            "sensitive": True,
        },
    )
    app_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "BigPanda application key",
            "hint": "Found under Settings > API Integrations when you create an integration",
            "sensitive": True,
        },
    )


class BigPandaProvider(BaseProvider):
    """Pull correlated incidents from BigPanda AIOps platform into Keep."""

    PROVIDER_DISPLAY_NAME = "BigPanda"
    PROVIDER_TAGS = ["alert", "monitoring", "aiops"]
    PROVIDER_CATEGORY = ["Incident Management", "Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incidents:read",
            description="Read incidents from BigPanda",
            mandatory=True,
            alias="Read Incidents",
            documentation_url="https://docs.bigpanda.io/reference",
        ),
    ]

    # BigPanda status → Keep status
    _STATUS_MAP = {
        "active": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
        "ok": AlertStatus.RESOLVED,
        "snoozed": AlertStatus.SUPPRESSED,
    }

    # BigPanda severity → Keep severity
    _SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
        "ok": AlertSeverity.INFO,
        "unknown": AlertSeverity.INFO,
    }

    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = BigPandaProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "X-BP-App-Key": self.authentication_config.app_key,
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes by testing the incidents endpoint."""
        scopes: dict[str, bool | str] = {}
        try:
            resp = requests.get(
                f"{BIGPANDA_API_BASE}/incidents",
                headers=self._get_headers(),
                params={"limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                scopes["incidents:read"] = True
            elif resp.status_code == 401:
                scopes["incidents:read"] = "Unauthorized — check your API token"
            elif resp.status_code == 403:
                scopes["incidents:read"] = "Forbidden — check your app key permissions"
            else:
                scopes["incidents:read"] = f"Unexpected status: {resp.status_code}"
        except Exception as e:
            self.logger.exception("Failed to validate BigPanda scopes")
            scopes["incidents:read"] = str(e)
        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """Pull active and recent incidents from BigPanda."""
        self.logger.info("Fetching incidents from BigPanda")
        alerts: List[AlertDto] = []
        page = 0
        page_size = 100

        while True:
            try:
                resp = requests.get(
                    f"{BIGPANDA_API_BASE}/incidents",
                    headers=self._get_headers(),
                    params={
                        "limit": page_size,
                        "skip": page * page_size,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                self.logger.error(
                    "Error fetching BigPanda incidents (page %d): %s", page, e
                )
                break

            data = resp.json()
            # BigPanda returns {"incidents": [...], "metadata": {...}}
            incidents = data if isinstance(data, list) else data.get("incidents", [])

            if not incidents:
                break

            for incident in incidents:
                alert = self._incident_to_alert(incident)
                if alert:
                    alerts.append(alert)

            if len(incidents) < page_size:
                break
            page += 1

        self.logger.info("Fetched %d BigPanda incidents", len(alerts))
        return alerts

    def _incident_to_alert(self, incident: dict) -> "Optional[AlertDto]":
        """Map a BigPanda incident dict to a Keep AlertDto."""
        try:
            incident_id = str(incident.get("id", ""))
            title = (
                incident.get("title")
                or incident.get("description")
                or f"BigPanda Incident #{incident_id}"
            )

            status_raw = str(incident.get("status", "active")).lower()
            severity_raw = str(incident.get("severity", "unknown")).lower()

            created_at = incident.get("created_at") or incident.get("start")
            updated_at = incident.get("updated_at") or incident.get("end") or created_at

            if updated_at:
                try:
                    # BigPanda may return epoch seconds
                    if isinstance(updated_at, (int, float)):
                        last_received = datetime.datetime.utcfromtimestamp(updated_at)
                    else:
                        last_received = datetime.datetime.fromisoformat(
                            str(updated_at).replace("Z", "+00:00")
                        )
                except (ValueError, AttributeError, OSError):
                    last_received = datetime.datetime.utcnow()
            else:
                last_received = datetime.datetime.utcnow()

            assignee = ""
            if incident.get("assignee"):
                a = incident["assignee"]
                if isinstance(a, dict):
                    assignee = a.get("name") or a.get("email", "")
                else:
                    assignee = str(a)

            url = (
                incident.get("url")
                or incident.get("permalink")
                or f"https://app.bigpanda.io/app/incidents/{incident_id}"
            )

            environments = incident.get("environments", [])
            environment = environments[0] if environments else ""

            source_systems = incident.get("source", incident.get("sources", ["bigpanda"]))
            if not source_systems:
                source_systems = ["bigpanda"]

            return AlertDto(
                id=incident_id,
                name=title,
                severity=self._SEVERITY_MAP.get(severity_raw, AlertSeverity.INFO),
                status=self._STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                lastReceived=last_received,
                description=incident.get("description") or title,
                source=["bigpanda"],
                url=url,
                fingerprint=incident_id,
                assignee=assignee,
                labels=incident.get("tags", []),
                service=incident.get("service", ""),
                environment=environment,
            )
        except Exception as e:
            self.logger.error(
                "Failed to map BigPanda incident to AlertDto: %s", e
            )
            return None

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a BigPanda webhook payload into a Keep AlertDto."""
        status_map = {
            "active": AlertStatus.FIRING,
            "acknowledged": AlertStatus.ACKNOWLEDGED,
            "resolved": AlertStatus.RESOLVED,
            "ok": AlertStatus.RESOLVED,
            "snoozed": AlertStatus.SUPPRESSED,
        }
        severity_map = {
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.HIGH,
            "warning": AlertSeverity.WARNING,
            "medium": AlertSeverity.WARNING,
            "low": AlertSeverity.LOW,
            "info": AlertSeverity.INFO,
            "ok": AlertSeverity.INFO,
        }

        status_raw = str(event.get("status", "active")).lower()
        severity_raw = str(event.get("severity", "unknown")).lower()

        ts = event.get("updated_at") or event.get("created_at") or event.get("start")
        if ts:
            try:
                if isinstance(ts, (int, float)):
                    last_received = datetime.datetime.utcfromtimestamp(ts)
                else:
                    last_received = datetime.datetime.fromisoformat(
                        str(ts).replace("Z", "+00:00")
                    )
            except (ValueError, AttributeError, OSError):
                last_received = datetime.datetime.utcnow()
        else:
            last_received = datetime.datetime.utcnow()

        incident_id = str(event.get("id", ""))
        title = event.get("title") or event.get("description") or f"BigPanda Incident #{incident_id}"

        return AlertDto(
            id=incident_id,
            name=title,
            severity=severity_map.get(severity_raw, AlertSeverity.INFO),
            status=status_map.get(status_raw, AlertStatus.FIRING),
            lastReceived=last_received,
            description=event.get("description") or title,
            source=["bigpanda"],
            url=event.get("url") or f"https://app.bigpanda.io/app/incidents/{incident_id}",
            fingerprint=incident_id,
            service=event.get("service", ""),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_token = os.environ.get("BIGPANDA_API_TOKEN")
    app_key = os.environ.get("BIGPANDA_APP_KEY")
    if not api_token or not app_key:
        raise EnvironmentError("BIGPANDA_API_TOKEN and BIGPANDA_APP_KEY must be set")

    config = ProviderConfig(
        description="BigPanda Provider",
        authentication={"api_token": api_token, "app_key": app_key},
    )
    provider = BigPandaProvider(
        context_manager, provider_id="bigpanda-test", config=config
    )
    print(provider.validate_scopes())
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} alerts")
    for a in alerts:
        print(f"  - {a.name}: {a.severity} ({a.status})")
