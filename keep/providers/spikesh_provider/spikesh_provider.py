"""
SpikeshProvider is a class that provides alerting integration with Spike.sh,
an on-call and incident management platform.
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


@pydantic.dataclasses.dataclass
class SpikeshProviderAuthConfig:
    """
    SpikeshProviderAuthConfig holds authentication configuration for Spike.sh.
    """

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Spike.sh API Token",
            "hint": "Found in your Spike.sh account under Settings > API Tokens",
            "sensitive": True,
        },
    )

    integration_token: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Spike.sh Integration Webhook Token",
            "hint": "The webhook token from a Spike.sh integration (used for sending alerts)",
            "sensitive": True,
        },
        default=None,
    )


class SpikeshProvider(BaseProvider):
    """Send alerts and manage incidents via Spike.sh on-call platform."""

    PROVIDER_DISPLAY_NAME = "Spike.sh"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Incident Management"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="incidents:read",
            description="Read incidents from Spike.sh",
            mandatory=True,
            alias="Read Incidents",
        ),
        ProviderScope(
            name="incidents:write",
            description="Create and acknowledge incidents in Spike.sh",
            mandatory=False,
            alias="Write Incidents",
        ),
    ]

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "triggered": AlertStatus.FIRING,
        "acknowledged": AlertStatus.ACKNOWLEDGED,
        "resolved": AlertStatus.RESOLVED,
    }

    FINGERPRINT_FIELDS = ["id"]

    BASE_URL = "https://api.spike.sh/v1"

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = SpikeshProviderAuthConfig(
            **self.config.authentication
        )

    def __get_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "Content-Type": "application/json",
        }

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate provider scopes by querying the incidents endpoint."""
        scopes = {}
        try:
            response = requests.get(
                f"{self.BASE_URL}/incidents",
                headers=self.__get_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                scopes["incidents:read"] = True
            elif response.status_code == 403:
                scopes["incidents:read"] = "Insufficient permissions to read incidents"
            else:
                scopes["incidents:read"] = (
                    f"Unable to read incidents from Spike.sh, status code: {response.status_code}"
                )
        except Exception as e:
            self.logger.exception("Failed to validate Spike.sh scopes")
            scopes["incidents:read"] = str(e)

        # Check write scope via the integration token presence
        if self.authentication_config.integration_token:
            scopes["incidents:write"] = True
        else:
            scopes["incidents:write"] = "No integration token configured"

        return scopes

    def _get_alerts(self) -> List[AlertDto]:
        """Pull incidents from Spike.sh as alerts."""
        self.logger.info("Fetching incidents from Spike.sh")
        alerts = []
        try:
            response = requests.get(
                f"{self.BASE_URL}/incidents",
                headers=self.__get_headers(),
                params={"limit": 100, "status": "triggered"},
                timeout=10,
            )
            if not response.ok:
                self.logger.error(
                    "Failed to fetch incidents from Spike.sh: %s", response.text
                )
                raise Exception(
                    f"Failed to fetch incidents from Spike.sh: {response.status_code}"
                )

            data = response.json()
            items = data.get("incidents", data) if isinstance(data, dict) else data
            if not isinstance(items, list):
                items = []

            for item in items:
                severity_raw = item.get("severity", "critical").lower()
                status_raw = item.get("status", "triggered").lower()

                created_at = item.get("created_at") or item.get("triggeredAt")
                if created_at:
                    try:
                        last_received = datetime.datetime.fromisoformat(
                            created_at.replace("Z", "+00:00")
                        )
                    except (ValueError, AttributeError):
                        last_received = datetime.datetime.utcnow()
                else:
                    last_received = datetime.datetime.utcnow()

                alert = AlertDto(
                    id=str(item.get("id", "")),
                    name=item.get("title", item.get("name", "Spike.sh Incident")),
                    severity=self.SEVERITIES_MAP.get(severity_raw, AlertSeverity.HIGH),
                    status=self.STATUS_MAP.get(status_raw, AlertStatus.FIRING),
                    lastReceived=last_received,
                    description=item.get("description", ""),
                    source=["spikesh"],
                    url=item.get("url", ""),
                    fingerprint=str(item.get("id", "")),
                    service=item.get("integration", {}).get("name", "") if isinstance(item.get("integration"), dict) else "",
                )
                alerts.append(alert)
        except Exception as e:
            self.logger.error("Error fetching incidents from Spike.sh: %s", e)
        return alerts

    def notify(
        self,
        alert_message: str = "",
        alert_description: str = "",
        severity: str = "critical",
        **kwargs: dict,
    ):
        """
        Send an alert to Spike.sh via webhook integration.

        Args:
            alert_message: Title/message of the alert
            alert_description: Detailed description
            severity: Alert severity level (critical, high, warning, info)
        """
        if not self.authentication_config.integration_token:
            raise Exception("integration_token is required to send alerts to Spike.sh")

        self.logger.info("Sending alert to Spike.sh: %s", alert_message)
        payload = {
            "title": alert_message,
            "description": alert_description,
            "severity": severity,
        }
        payload.update(kwargs)

        response = requests.post(
            f"https://hooks.spike.sh/{self.authentication_config.integration_token}",
            json=payload,
            timeout=10,
        )
        if not response.ok:
            raise Exception(
                f"Failed to send alert to Spike.sh: {response.status_code} - {response.text}"
            )
        self.logger.info("Successfully sent alert to Spike.sh")
        return response.json() if response.text else {"status": "ok"}

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """Format a Spike.sh webhook payload into an AlertDto."""
        severity_raw = event.get("severity", "critical").lower()
        status_raw = event.get("status", "triggered").lower()

        severity = SpikeshProvider.SEVERITIES_MAP.get(severity_raw, AlertSeverity.HIGH)
        status = SpikeshProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

        created_at = event.get("created_at") or event.get("triggeredAt")
        if created_at:
            try:
                last_received = datetime.datetime.fromisoformat(
                    str(created_at).replace("Z", "+00:00")
                )
            except (ValueError, AttributeError):
                last_received = datetime.datetime.utcnow()
        else:
            last_received = datetime.datetime.utcnow()

        return AlertDto(
            id=str(event.get("id", "")),
            name=event.get("title", event.get("name", "Spike.sh Incident")),
            severity=severity,
            status=status,
            lastReceived=last_received,
            description=event.get("description", ""),
            source=["spikesh"],
            url=event.get("url", ""),
            fingerprint=str(event.get("id", "")),
            service=event.get("integration_name", ""),
        )


if __name__ == "__main__":
    import logging
    import os

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    api_token = os.environ.get("SPIKESH_API_TOKEN")
    if not api_token:
        raise Exception("SPIKESH_API_TOKEN must be set")

    config = ProviderConfig(
        description="Spike.sh Provider",
        authentication={
            "api_token": api_token,
        },
    )
    provider = SpikeshProvider(
        context_manager, provider_id="spikesh-test", config=config
    )
    alerts = provider._get_alerts()
    print(f"Fetched {len(alerts)} incidents from Spike.sh")
    for alert in alerts:
        print(f"  - {alert.name}: {alert.severity} ({alert.status})")
