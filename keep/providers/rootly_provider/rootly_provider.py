"""
RootlyProvider is a class that integrates with Rootly incident management platform,
allowing Keep to pull incidents as alerts and receive webhook notifications.
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
class RootlyProviderAuthConfig:
    """
    RootlyProviderAuthConfig is a class that holds the authentication configuration
    for the Rootly provider.
    """

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Rootly API Key",
            "hint": "Found at https://rootly.com/account (Settings > API Keys)",
            "sensitive": True,
        },
    )


class RootlyProvider(BaseProvider):
    """Pull incidents and alerts from Rootly incident management platform."""

    PROVIDER_DISPLAY_NAME = "Rootly"
    PROVIDER_CATEGORY = ["Incident Management"]
    PROVIDER_TAGS = ["alert"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated",
            mandatory=True,
            alias="authenticated",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "medium": AlertSeverity.MEDIUM,
        "low": AlertSeverity.LOW,
        "unknown": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "triggered": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
        "started": AlertStatus.FIRING,
        "in_progress": AlertStatus.FIRING,
        "mitigated": AlertStatus.ACKNOWLEDGED,
    }

    BASE_URL = "https://api.rootly.com/v1"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = RootlyProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Content-Type": "application/vnd.api+json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that the API key is valid."""
        try:
            response = requests.get(
                f"{self.BASE_URL}/incidents",
                headers=self.__get_headers(),
                params={"page[size]": 1},
                timeout=10,
            )
            if response.status_code == 200:
                return {"authenticated": True}
            elif response.status_code == 401:
                return {"authenticated": "Invalid API key"}
            else:
                return {
                    "authenticated": f"Unexpected status code: {response.status_code}"
                }
        except Exception as e:
            self.logger.error("Error validating Rootly scopes: %s", e)
            return {"authenticated": f"Error connecting to Rootly: {e}"}

    def _get_alerts(self) -> List[AlertDto]:
        """Pull incidents from Rootly and convert to AlertDto objects."""
        alerts = []
        page = 1
        page_size = 25

        try:
            while True:
                self.logger.info("Fetching Rootly incidents page %d", page)
                response = requests.get(
                    f"{self.BASE_URL}/incidents",
                    headers=self.__get_headers(),
                    params={
                        "page[number]": page,
                        "page[size]": page_size,
                    },
                    timeout=30,
                )

                if not response.ok:
                    self.logger.error(
                        "Failed to fetch incidents from Rootly: %s", response.text
                    )
                    break

                data = response.json()
                incidents = data.get("data", [])

                if not incidents:
                    break

                for incident in incidents:
                    alert = self.__incident_to_alert(incident)
                    alerts.append(alert)

                # Check if there are more pages
                meta = data.get("meta", {})
                total_pages = meta.get("total_pages", 1)
                if page >= total_pages:
                    break
                page += 1

        except Exception as e:
            self.logger.error("Error fetching incidents from Rootly: %s", e)

        return alerts

    def __incident_to_alert(self, incident: dict) -> AlertDto:
        """Convert a Rootly incident dict to an AlertDto."""
        attrs = incident.get("attributes", {})
        incident_id = incident.get("id", "unknown")

        severity_str = attrs.get("severity", {})
        if isinstance(severity_str, dict):
            severity_str = severity_str.get("data", {})
            if isinstance(severity_str, dict):
                severity_str = severity_str.get("attributes", {}).get("name", "unknown")
            else:
                severity_str = "unknown"

        severity = self.SEVERITIES_MAP.get(
            str(severity_str).lower(), AlertSeverity.INFO
        )

        status_str = attrs.get("status", "triggered")
        status = self.STATUS_MAP.get(str(status_str).lower(), AlertStatus.FIRING)

        created_at = attrs.get("created_at")
        if created_at:
            try:
                last_received = datetime.datetime.fromisoformat(
                    created_at.replace("Z", "+00:00")
                ).isoformat()
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow().isoformat()
        else:
            last_received = datetime.datetime.utcnow().isoformat()

        # Build URL to the incident
        slug = attrs.get("slug", incident_id)
        url = f"https://rootly.com/incidents/{slug}"

        return AlertDto(
            id=incident_id,
            name=attrs.get("title", f"Rootly Incident {incident_id}"),
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=attrs.get("summary", ""),
            source=["rootly"],
            url=url,
            labels={
                "environment": attrs.get("environment", {}).get("data", {}).get("attributes", {}).get("name", "") if isinstance(attrs.get("environment"), dict) else "",
                "service": attrs.get("service", {}).get("data", {}).get("attributes", {}).get("name", "") if isinstance(attrs.get("service"), dict) else "",
                "status": status_str,
            },
            fingerprint=incident_id,
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a webhook event from Rootly into an AlertDto."""
        incident = event.get("data", {})
        attrs = incident.get("attributes", event)

        severity_str = attrs.get("severity", "unknown")
        if isinstance(severity_str, dict):
            severity_str = severity_str.get("name", "unknown")

        severity = RootlyProvider.SEVERITIES_MAP.get(
            str(severity_str).lower(), AlertSeverity.INFO
        )

        status_str = attrs.get("status", event.get("action", "triggered"))
        status = RootlyProvider.STATUS_MAP.get(
            str(status_str).lower(), AlertStatus.FIRING
        )

        incident_id = incident.get("id", event.get("id", "unknown"))
        slug = attrs.get("slug", incident_id)

        return AlertDto(
            id=incident_id,
            name=attrs.get("title", f"Rootly Incident {incident_id}"),
            severity=severity,
            status=status,
            lastReceived=attrs.get(
                "created_at", datetime.datetime.utcnow().isoformat()
            ),
            description=attrs.get("summary", ""),
            source=["rootly"],
            url=f"https://rootly.com/incidents/{slug}",
            labels={
                "status": status_str,
                "action": event.get("action", ""),
            },
            fingerprint=incident_id,
        )
