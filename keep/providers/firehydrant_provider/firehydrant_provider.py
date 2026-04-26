"""
FireHydrantProvider integrates with FireHydrant incident management platform,
allowing Keep to pull active incidents as alerts and receive webhook notifications
for incident lifecycle events.
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
class FireHydrantProviderAuthConfig:
    """
    FireHydrantProviderAuthConfig holds authentication for the FireHydrant provider.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "FireHydrant Bot API Token",
            "hint": "Found at https://app.firehydrant.io/profile/bot-users — create a Bot User and copy the token",
            "sensitive": True,
        },
    )


class FireHydrantProvider(BaseProvider):
    """Pull active incidents from FireHydrant and receive real-time webhook events."""

    PROVIDER_DISPLAY_NAME = "FireHydrant"
    PROVIDER_CATEGORY = ["Incident Management"]
    PROVIDER_TAGS = ["alert", "incident"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated with FireHydrant API",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    # FireHydrant incident severity → Keep AlertSeverity
    SEVERITY_MAP = {
        "SEV1": AlertSeverity.CRITICAL,
        "SEV2": AlertSeverity.HIGH,
        "SEV3": AlertSeverity.WARNING,
        "SEV4": AlertSeverity.LOW,
        "SEV5": AlertSeverity.INFO,
    }

    # FireHydrant incident current milestone → Keep AlertStatus
    MILESTONE_STATUS_MAP = {
        "started": AlertStatus.FIRING,
        "detected": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "investigating": AlertStatus.FIRING,
        "identified": AlertStatus.FIRING,
        "mitigated": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
        "postmortem_started": AlertStatus.RESOLVED,
        "postmortem_completed": AlertStatus.RESOLVED,
        "closed": AlertStatus.RESOLVED,
    }

    BASE_URL = "https://api.firehydrant.io/v1"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = FireHydrantProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "Authorization": self.authentication_config.api_key,
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate API token by calling the ping endpoint."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/ping",
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"authenticated": True}
            elif response.status_code == 401:
                return {"authenticated": "Invalid or missing API token"}
            elif response.status_code == 403:
                return {"authenticated": "Access denied — check token permissions"}
            else:
                return {
                    "authenticated": f"Unexpected status: {response.status_code}"
                }
        except Exception as e:
            self.logger.error("Error validating FireHydrant scopes: %s", e)
            return {"authenticated": f"Error connecting to FireHydrant: {e}"}

    def _get_alerts(self) -> List[AlertDto]:
        """Pull active and recent incidents from FireHydrant."""
        alerts = []
        try:
            self.logger.info("Fetching incidents from FireHydrant")
            page = 1
            while True:
                response = requests.get(
                    f"{self.BASE_URL}/incidents",
                    headers=self.__get_headers(),
                    params={
                        "per_page": 50,
                        "page": page,
                    },
                    timeout=30,
                )

                if not response.ok:
                    self.logger.error(
                        "Failed to fetch FireHydrant incidents: %s", response.text
                    )
                    break

                data = response.json()
                incidents = data.get("data", [])

                if not incidents:
                    break

                for incident in incidents:
                    alerts.append(self.__incident_to_alert(incident))

                pagination = data.get("pagination", {})
                if page >= pagination.get("pages", 1):
                    break
                page += 1

        except Exception as e:
            self.logger.error("Error fetching FireHydrant incidents: %s", e)

        return alerts

    def __incident_to_alert(self, incident: dict) -> AlertDto:
        """Convert a FireHydrant incident to an AlertDto."""
        incident_id = incident.get("id", "unknown")
        name = incident.get("name", "Unknown Incident")
        summary = incident.get("description", "")
        severity_name = incident.get("severity", "SEV3")
        current_milestone = incident.get("current_milestone", "started")
        started_at = incident.get("started_at", incident.get("created_at", ""))

        severity = self.SEVERITY_MAP.get(severity_name, AlertSeverity.WARNING)
        status = self.MILESTONE_STATUS_MAP.get(
            current_milestone, AlertStatus.FIRING
        )

        if started_at:
            try:
                last_received = datetime.datetime.fromisoformat(
                    started_at.replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow().isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        url = f"https://app.firehydrant.io/incidents/{incident_id}"

        # Collect services and teams affected
        services = [
            s.get("name", "") for s in incident.get("services", [])
        ]
        teams = [
            t.get("name", "") for t in incident.get("teams", [])
        ]
        tags = [tag.get("name", "") for tag in incident.get("tags", [])]

        return AlertDto(
            id=incident_id,
            name=name,
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=summary,
            source=["firehydrant"],
            url=url,
            labels={
                "incident_id": incident_id,
                "severity": severity_name,
                "milestone": current_milestone,
                "services": ",".join(services),
                "teams": ",".join(teams),
                "tags": ",".join(tags),
            },
            fingerprint=incident_id,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a FireHydrant webhook payload into an AlertDto."""
        incident = event.get("incident", event)
        incident_id = incident.get("id", "unknown")
        name = incident.get("name", "Unknown Incident")
        summary = incident.get("description", "")
        severity_name = incident.get("severity", "SEV3")
        current_milestone = incident.get("current_milestone", "started")

        severity_map = {
            "SEV1": AlertSeverity.CRITICAL,
            "SEV2": AlertSeverity.HIGH,
            "SEV3": AlertSeverity.WARNING,
            "SEV4": AlertSeverity.LOW,
            "SEV5": AlertSeverity.INFO,
        }
        milestone_status_map = {
            "started": AlertStatus.FIRING,
            "detected": AlertStatus.FIRING,
            "acknowledged": AlertStatus.ACKNOWLEDGED,
            "investigating": AlertStatus.FIRING,
            "identified": AlertStatus.FIRING,
            "mitigated": AlertStatus.FIRING,
            "resolved": AlertStatus.RESOLVED,
            "postmortem_started": AlertStatus.RESOLVED,
            "postmortem_completed": AlertStatus.RESOLVED,
            "closed": AlertStatus.RESOLVED,
        }

        severity = severity_map.get(severity_name, AlertSeverity.WARNING)
        status = milestone_status_map.get(current_milestone, AlertStatus.FIRING)

        url = f"https://app.firehydrant.io/incidents/{incident_id}"
        services = [s.get("name", "") for s in incident.get("services", [])]
        teams = [t.get("name", "") for t in incident.get("teams", [])]

        return AlertDto(
            id=incident_id,
            name=name,
            severity=severity,
            status=status,
            lastReceived=datetime.datetime.utcnow().isoformat(),
            description=summary,
            source=["firehydrant"],
            url=url,
            labels={
                "incident_id": incident_id,
                "severity": severity_name,
                "milestone": current_milestone,
                "services": ",".join(services),
                "teams": ",".join(teams),
                "event_type": event.get("event", ""),
            },
            fingerprint=incident_id,
        )
