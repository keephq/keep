"""
BlamelessProvider integrates Keep with Blameless, an SRE platform for
structured incident management, blameless retrospectives, and SLO tracking.
It pulls active incidents from the Blameless REST API so teams can correlate
reliability events across their entire observability stack.
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

BLAMELESS_API_BASE = "https://api.blameless.io/api/v1"


@pydantic.dataclasses.dataclass
class BlamelessProviderAuthConfig:
    """
    Authentication configuration for Blameless.
    """

    client_id: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Blameless OAuth client ID",
            "hint": "Found under Settings > Integrations > API in Blameless",
            "sensitive": False,
        },
    )
    client_secret: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Blameless OAuth client secret",
            "hint": "Found under Settings > Integrations > API in Blameless",
            "sensitive": True,
        },
    )
    base_url: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Blameless instance base URL",
            "hint": "e.g. https://your-org.blameless.io (defaults to https://api.blameless.io)",
            "validation": "any_http_url",
        },
        default=BLAMELESS_API_BASE,
    )


class BlamelessProvider(BaseProvider):
    """Pull structured incidents from Blameless SRE platform into Keep."""

    PROVIDER_DISPLAY_NAME = "Blameless"
    PROVIDER_TAGS = ["incident", "monitoring", "sre"]
    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incidents:read",
            description="Read incidents from Blameless",
            mandatory=True,
            alias="Read Incidents",
            documentation_url="https://api.blameless.io/",
        ),
    ]

    # Blameless severity → Keep severity
    # SEV1 = most severe, SEV5 = least severe
    _SEVERITY_MAP = {
        "sev1": AlertSeverity.CRITICAL,
        "sev0": AlertSeverity.CRITICAL,
        "sev2": AlertSeverity.HIGH,
        "sev3": AlertSeverity.WARNING,
        "sev4": AlertSeverity.LOW,
        "sev5": AlertSeverity.INFO,
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "medium": AlertSeverity.WARNING,
        "warning": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
    }

    # Blameless status → Keep status
    _STATUS_MAP = {
        "active": AlertStatus.FIRING,
        "investigating": AlertStatus.FIRING,
        "identified": AlertStatus.FIRING,
        "monitoring": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "closed": AlertStatus.RESOLVED,
        "cancelled": AlertStatus.RESOLVED,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
    }

    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self._access_token: Optional[str] = None

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = BlamelessProviderAuthConfig(
            **self.config.authentication
        )

    def _get_access_token(self) -> str:
        """Obtain a short-lived access token using client credentials."""
        if self._access_token:
            return self._access_token

        resp = requests.post(
            "https://auth.blameless.io/oauth/token",
            json={
                "grant_type": "client_credentials",
                "client_id": self.authentication_config.client_id,
                "client_secret": self.authentication_config.client_secret,
                "audience": "https://api.blameless.io",
            },
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data.get("access_token", "")
        return self._access_token

    def _get_headers(self) -> dict:
        token = self._get_access_token()
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _api_base(self) -> str:
        base = str(self.authentication_config.base_url).rstrip("/")
        # If the user set a custom base_url that doesn't end in /api/v1, don't double it
        if not base.endswith("/api/v1"):
            base = f"{base}/api/v1"
        return base

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes by testing the incidents endpoint."""
        scopes: dict[str, bool | str] = {}
        try:
            resp = requests.get(
                f"{self._api_base()}/incidents",
                headers=self._get_headers(),
                params={"limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                scopes["incidents:read"] = True
            elif resp.status_code == 401:
                scopes["incidents:read"] = "Unauthorized — check your client credentials"
            elif resp.status_code == 403:
                scopes["incidents:read"] = "Forbidden — insufficient OAuth scope"
            else:
                scopes["incidents:read"] = f"Unexpected status: {resp.status_code}"
        except Exception as e:
            self.logger.exception("Failed to validate Blameless scopes")
            scopes["incidents:read"] = str(e)
        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """Pull active and recent incidents from Blameless."""
        self.logger.info("Fetching incidents from Blameless")
        alerts: List[AlertDto] = []
        page = 1
        page_size = 50

        while True:
            try:
                resp = requests.get(
                    f"{self._api_base()}/incidents",
                    headers=self._get_headers(),
                    params={
                        "page": page,
                        "limit": page_size,
                        "status": "active,investigating,identified,monitoring",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                self.logger.error(
                    "Error fetching Blameless incidents (page %d): %s", page, e
                )
                break

            data = resp.json()
            incidents = (
                data
                if isinstance(data, list)
                else data.get("incidents", data.get("data", []))
            )

            if not incidents:
                break

            for incident in incidents:
                alert = self._incident_to_alert(incident)
                if alert:
                    alerts.append(alert)

            if len(incidents) < page_size:
                break
            page += 1

        self.logger.info("Fetched %d Blameless incidents", len(alerts))
        return alerts

    def _incident_to_alert(self, incident: dict) -> "Optional[AlertDto]":
        """Map a Blameless incident dict to a Keep AlertDto."""
        try:
            incident_id = str(incident.get("id", ""))
            title = (
                incident.get("title")
                or incident.get("name")
                or f"Blameless Incident #{incident_id}"
            )

            severity_raw = str(
                incident.get("severity", incident.get("severity_label", "sev3"))
            ).lower()
            status_raw = str(incident.get("status", "active")).lower()

            created_at = incident.get("created_at") or incident.get("startedAt")
            updated_at = (
                incident.get("updated_at")
                or incident.get("updatedAt")
                or created_at
            )

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
                a = incident["assignee"]
                if isinstance(a, dict):
                    assignee = a.get("name") or a.get("email", "")
                else:
                    assignee = str(a)

            url = incident.get("url") or f"https://app.blameless.io/incidents/{incident_id}"

            services = incident.get("services", [])
            service = services[0] if isinstance(services, list) and services else ""

            environments = incident.get("environments", [])
            environment = (
                environments[0] if isinstance(environments, list) and environments else ""
            )

            labels = incident.get("labels", incident.get("tags", []))

            return AlertDto(
                id=incident_id,
                name=title,
                severity=self._SEVERITY_MAP.get(severity_raw, AlertSeverity.WARNING),
                status=self._STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                lastReceived=last_received,
                description=incident.get("description") or title,
                source=["blameless"],
                url=url,
                fingerprint=incident_id,
                assignee=assignee,
                service=service,
                environment=environment,
                labels=labels if isinstance(labels, list) else [],
            )
        except Exception as e:
            self.logger.error(
                "Failed to map Blameless incident to AlertDto: %s", e
            )
            return None

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a Blameless webhook payload into a Keep AlertDto."""
        severity_map = {
            "sev0": AlertSeverity.CRITICAL,
            "sev1": AlertSeverity.CRITICAL,
            "sev2": AlertSeverity.HIGH,
            "sev3": AlertSeverity.WARNING,
            "sev4": AlertSeverity.LOW,
            "sev5": AlertSeverity.INFO,
            "critical": AlertSeverity.CRITICAL,
            "high": AlertSeverity.HIGH,
            "medium": AlertSeverity.WARNING,
            "low": AlertSeverity.LOW,
        }
        status_map = {
            "active": AlertStatus.FIRING,
            "investigating": AlertStatus.FIRING,
            "identified": AlertStatus.FIRING,
            "monitoring": AlertStatus.FIRING,
            "resolved": AlertStatus.RESOLVED,
            "closed": AlertStatus.RESOLVED,
            "acknowledged": AlertStatus.ACKNOWLEDGED,
        }

        severity_raw = str(
            event.get("severity", event.get("severity_label", "sev3"))
        ).lower()
        status_raw = str(event.get("status", "active")).lower()

        ts = event.get("updated_at") or event.get("created_at")
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
        title = (
            event.get("title")
            or event.get("name")
            or f"Blameless Incident #{incident_id}"
        )

        return AlertDto(
            id=incident_id,
            name=title,
            severity=severity_map.get(severity_raw, AlertSeverity.WARNING),
            status=status_map.get(status_raw, AlertStatus.FIRING),
            lastReceived=last_received,
            description=event.get("description") or title,
            source=["blameless"],
            url=event.get("url") or f"https://app.blameless.io/incidents/{incident_id}",
            fingerprint=incident_id,
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    client_id = os.environ.get("BLAMELESS_CLIENT_ID")
    client_secret = os.environ.get("BLAMELESS_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise EnvironmentError(
            "BLAMELESS_CLIENT_ID and BLAMELESS_CLIENT_SECRET must be set"
        )

    config = ProviderConfig(
        description="Blameless Provider",
        authentication={"client_id": client_id, "client_secret": client_secret},
    )
    provider = BlamelessProvider(
        context_manager, provider_id="blameless-test", config=config
    )
    print(provider.validate_scopes())
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} incidents")
    for a in alerts:
        print(f"  - {a.name}: {a.severity} ({a.status})")
