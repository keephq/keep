"""
MoogsoftProvider integrates Keep with Moogsoft, an AIOps platform that uses
machine learning to detect, correlate, and prioritize IT incidents (called
"situations") from raw alert noise across monitoring tools.
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
class MoogsoftProviderAuthConfig:
    """
    Authentication configuration for Moogsoft.
    """

    api_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Moogsoft instance base URL",
            "hint": "e.g. https://your-company.moogsoft.com",
            "validation": "any_http_url",
        },
    )
    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Moogsoft API token",
            "hint": "Generate under User Settings > API Tokens in Moogsoft",
            "sensitive": True,
        },
    )


class MoogsoftProvider(BaseProvider):
    """Pull ML-correlated situations (incidents) from Moogsoft into Keep."""

    PROVIDER_DISPLAY_NAME = "Moogsoft"
    PROVIDER_TAGS = ["alert", "monitoring", "aiops"]
    PROVIDER_CATEGORY = ["Incident Management", "Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="situations:read",
            description="Read situations (correlated incidents) from Moogsoft",
            mandatory=True,
            alias="Read Situations",
            documentation_url="https://docs.moogsoft.com/",
        ),
    ]

    # Moogsoft numeric severity (1-5) → Keep severity
    # 5 = Critical, 4 = Major, 3 = Minor, 2 = Warning, 1 = Info
    _SEVERITY_MAP = {
        5: AlertSeverity.CRITICAL,
        4: AlertSeverity.HIGH,
        3: AlertSeverity.WARNING,
        2: AlertSeverity.LOW,
        1: AlertSeverity.INFO,
    }
    # String severity names (also supported)
    _SEVERITY_STR_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "major": AlertSeverity.HIGH,
        "minor": AlertSeverity.WARNING,
        "warning": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
        "clear": AlertSeverity.INFO,
    }

    # Moogsoft situation status → Keep status
    _STATUS_MAP = {
        "open": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
        "closed": AlertStatus.RESOLVED,
        "snoozed": AlertStatus.SUPPRESSED,
    }

    FINGERPRINT_FIELDS = ["id"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = MoogsoftProviderAuthConfig(
            **self.config.authentication
        )

    def _base_url(self) -> str:
        url = str(self.authentication_config.api_url).rstrip("/")
        return url

    def _get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes by querying the situations endpoint."""
        scopes: dict[str, bool | str] = {}
        try:
            resp = requests.get(
                f"{self._base_url()}/api/v1/situations",
                headers=self._get_headers(),
                params={"limit": 1},
                timeout=10,
            )
            if resp.status_code == 200:
                scopes["situations:read"] = True
            elif resp.status_code == 401:
                scopes["situations:read"] = "Unauthorized — check your API token"
            elif resp.status_code == 403:
                scopes["situations:read"] = "Forbidden — insufficient permissions"
            else:
                scopes["situations:read"] = f"Unexpected status: {resp.status_code}"
        except Exception as e:
            self.logger.exception("Failed to validate Moogsoft scopes")
            scopes["situations:read"] = str(e)
        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """Pull active situations from Moogsoft."""
        self.logger.info("Fetching situations from Moogsoft")
        alerts: List[AlertDto] = []
        page = 0
        page_size = 100

        while True:
            try:
                resp = requests.get(
                    f"{self._base_url()}/api/v1/situations",
                    headers=self._get_headers(),
                    params={
                        "limit": page_size,
                        "offset": page * page_size,
                        "status": "Open,Acknowledged",
                    },
                    timeout=15,
                )
                resp.raise_for_status()
            except requests.RequestException as e:
                self.logger.error(
                    "Error fetching Moogsoft situations (page %d): %s", page, e
                )
                break

            data = resp.json()
            # Response may be list or {"situations": [...]}
            situations = (
                data
                if isinstance(data, list)
                else data.get("situations", data.get("data", []))
            )

            if not situations:
                break

            for situation in situations:
                alert = self._situation_to_alert(situation)
                if alert:
                    alerts.append(alert)

            if len(situations) < page_size:
                break
            page += 1

        self.logger.info("Fetched %d Moogsoft situations", len(alerts))
        return alerts

    def _map_severity(self, situation: dict) -> AlertSeverity:
        """Map Moogsoft severity (int or string) to AlertSeverity."""
        sev = situation.get("severity")
        if isinstance(sev, int):
            return self._SEVERITY_MAP.get(sev, AlertSeverity.INFO)
        if isinstance(sev, str):
            return self._SEVERITY_STR_MAP.get(sev.lower(), AlertSeverity.INFO)
        return AlertSeverity.INFO

    def _situation_to_alert(self, situation: dict) -> "Optional[AlertDto]":
        """Map a Moogsoft situation dict to a Keep AlertDto."""
        try:
            sit_id = str(situation.get("id", ""))
            title = (
                situation.get("description")
                or situation.get("name")
                or f"Moogsoft Situation #{sit_id}"
            )

            status_raw = str(situation.get("status", "Open")).lower()
            created_at = situation.get("created_at") or situation.get("create_time")
            modified_at = (
                situation.get("modified_at")
                or situation.get("modify_time")
                or created_at
            )

            if modified_at:
                try:
                    if isinstance(modified_at, (int, float)):
                        last_received = datetime.datetime.utcfromtimestamp(modified_at)
                    else:
                        last_received = datetime.datetime.fromisoformat(
                            str(modified_at).replace("Z", "+00:00")
                        )
                except (ValueError, AttributeError, OSError):
                    last_received = datetime.datetime.utcnow()
            else:
                last_received = datetime.datetime.utcnow()

            assignee = situation.get("assignee", "")
            if isinstance(assignee, dict):
                assignee = assignee.get("name") or assignee.get("email", "")

            services = situation.get("services", [])
            service = services[0] if services else ""

            url = (
                situation.get("url")
                or f"{self._base_url()}/situations/{sit_id}"
            )

            return AlertDto(
                id=sit_id,
                name=title,
                severity=self._map_severity(situation),
                status=self._STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                lastReceived=last_received,
                description=title,
                source=["moogsoft"],
                url=url,
                fingerprint=sit_id,
                assignee=str(assignee) if assignee else "",
                service=service,
                labels=situation.get("tags", situation.get("teams", [])),
            )
        except Exception as e:
            self.logger.error(
                "Failed to map Moogsoft situation to AlertDto: %s", e
            )
            return None

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a Moogsoft webhook payload into a Keep AlertDto."""
        severity_map = {
            5: AlertSeverity.CRITICAL,
            4: AlertSeverity.HIGH,
            3: AlertSeverity.WARNING,
            2: AlertSeverity.LOW,
            1: AlertSeverity.INFO,
            "critical": AlertSeverity.CRITICAL,
            "major": AlertSeverity.HIGH,
            "minor": AlertSeverity.WARNING,
            "warning": AlertSeverity.LOW,
            "info": AlertSeverity.INFO,
        }
        status_map = {
            "open": AlertStatus.FIRING,
            "acknowledged": AlertStatus.ACKNOWLEDGED,
            "resolved": AlertStatus.RESOLVED,
            "closed": AlertStatus.RESOLVED,
        }

        sev = event.get("severity")
        if isinstance(sev, str):
            severity = severity_map.get(sev.lower(), AlertSeverity.INFO)
        else:
            severity = severity_map.get(sev, AlertSeverity.INFO)

        status_raw = str(event.get("status", "open")).lower()
        ts = event.get("modified_at") or event.get("created_at")

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

        sit_id = str(event.get("id", ""))
        title = event.get("description") or event.get("name") or f"Moogsoft Situation #{sit_id}"

        return AlertDto(
            id=sit_id,
            name=title,
            severity=severity,
            status=status_map.get(status_raw, AlertStatus.FIRING),
            lastReceived=last_received,
            description=title,
            source=["moogsoft"],
            url=event.get("url", ""),
            fingerprint=sit_id,
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_url = os.environ.get("MOOGSOFT_API_URL", "https://your-company.moogsoft.com")
    api_token = os.environ.get("MOOGSOFT_API_TOKEN")
    if not api_token:
        raise EnvironmentError("MOOGSOFT_API_TOKEN must be set")

    config = ProviderConfig(
        description="Moogsoft Provider",
        authentication={"api_url": api_url, "api_token": api_token},
    )
    provider = MoogsoftProvider(
        context_manager, provider_id="moogsoft-test", config=config
    )
    print(provider.validate_scopes())
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} situations")
    for a in alerts:
        print(f"  - {a.name}: {a.severity} ({a.status})")
