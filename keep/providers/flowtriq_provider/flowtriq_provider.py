"""
Flowtriq Provider is a class that allows receiving DDoS incident alerts from Flowtriq
and querying the Flowtriq API for incident enrichment.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class FlowtriqProviderAuthConfig:
    """Flowtriq authentication configuration."""

    api_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Flowtriq API URL",
            "hint": "e.g. https://app.flowtriq.com",
            "validation": "any_http_url",
        }
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Flowtriq API key",
            "sensitive": True,
        }
    )


class FlowtriqProvider(BaseProvider):
    """Receive DDoS incident alerts from Flowtriq and query the Flowtriq API."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send DDoS incident alerts from Flowtriq to Keep, configure a webhook in your Flowtriq dashboard:

1. Log in to your Flowtriq dashboard.
2. Navigate to Settings > Integrations > Webhooks.
3. Click "Add Webhook".
4. Set the webhook URL to {keep_webhook_api_url}.
5. Add a header with key "X-API-KEY" and value {api_key}.
6. Select the incident events you want to forward (e.g. incident detected, incident resolved).
7. Save the webhook configuration.
"""

    PROVIDER_DISPLAY_NAME = "Flowtriq"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read DDoS incident alerts from Flowtriq",
        ),
    ]

    FINGERPRINT_FIELDS = ["id", "node_ip_address"]

    # Map Flowtriq severity levels to Keep severity levels.
    # Flowtriq classifies attacks by volume and impact.
    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "low": AlertSeverity.LOW,
        "info": AlertSeverity.INFO,
    }

    # Map Flowtriq incident status to Keep alert status.
    STATUS_MAP = {
        "active": AlertStatus.FIRING,
        "ongoing": AlertStatus.FIRING,
        "mitigated": AlertStatus.RESOLVED,
        "ended": AlertStatus.RESOLVED,
        "resolved": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = FlowtriqProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that the API key has read access by hitting the incidents endpoint."""
        self.logger.info("Validating Flowtriq provider scopes")
        try:
            response = requests.get(
                url=f"{self.authentication_config.api_url}/api/v1/incidents",
                headers=self._build_headers(),
                timeout=10,
            )
            if response.status_code == 200:
                return {"read_alerts": True}
            elif response.status_code in (401, 403):
                return {"read_alerts": "Authentication failed. Check your API key."}
            else:
                return {
                    "read_alerts": f"Unexpected status code: {response.status_code}"
                }
        except Exception as e:
            self.logger.exception("Failed to validate Flowtriq scopes")
            return {"read_alerts": str(e)}

    def _build_headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.authentication_config.api_key}",
            "Accept": "application/json",
        }

    def _get_alerts(self) -> list[AlertDto]:
        """Pull active incidents from the Flowtriq API."""
        self.logger.info("Fetching incidents from Flowtriq")
        try:
            response = requests.get(
                url=f"{self.authentication_config.api_url}/api/v1/incidents",
                headers=self._build_headers(),
                timeout=30,
            )
            response.raise_for_status()
            data = response.json()

            alerts = []
            for event in data.get("incidents", []):
                # API list responses use the same nested structure as webhooks
                alerts.append(self._format_alert(event))
            return alerts

        except Exception as e:
            self.logger.exception("Failed to fetch incidents from Flowtriq")
            raise Exception(f"Failed to fetch incidents from Flowtriq: {e}")

    def _query(self, incident_id: str = "", **kwargs) -> dict:
        """
        Query Flowtriq API for incident details (enrichment).

        Args:
            incident_id: The Flowtriq incident UUID to look up.

        Returns:
            dict: Full incident details from Flowtriq.
        """
        if not incident_id:
            raise ValueError("incident_id is required for Flowtriq queries")

        self.logger.info(
            "Querying Flowtriq incident", extra={"incident_id": incident_id}
        )
        try:
            response = requests.get(
                url=f"{self.authentication_config.api_url}/api/v1/incidents/{incident_id}",
                headers=self._build_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.exception(
                "Failed to query Flowtriq incident",
                extra={"incident_id": incident_id},
            )
            raise Exception(
                f"Failed to query Flowtriq incident {incident_id}: {e}"
            )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Flowtriq webhook event or API response into a Keep AlertDto.

        Flowtriq webhook payloads use a nested structure:
        - incident.id: unique incident identifier (UUID)
        - incident.title: human-readable title
        - incident.severity: critical, high, warning, low, info
        - incident.status: active, ongoing, mitigated, ended, resolved
        - incident.attack_family: classification (e.g. udp_flood, syn_flood)
        - incident.peak_bps: peak attack bandwidth in bits per second
        - incident.peak_pps: peak attack packet rate
        - incident.source_ip_count: number of unique source IPs
        - incident.duration_seconds: attack duration so far
        - incident.started_at: ISO timestamp of attack start
        - incident.resolved_at: ISO timestamp of resolution (null if active)
        - incident.dashboard_url: link to Flowtriq dashboard
        - incident.description: human-readable summary
        - node.name: name of the target node
        - node.ip_address: IP address of the target node
        """
        incident = event.get("incident", {})
        node = event.get("node", {})

        attack_id = incident.get("id")
        node_ip = node.get("ip_address", "unknown")
        node_name = node.get("name")
        attack_family = incident.get("attack_family", "DDoS Attack")
        raw_severity = incident.get("severity", "info")
        raw_status = incident.get("status", "active")

        severity = FlowtriqProvider.SEVERITIES_MAP.get(
            raw_severity.lower(), AlertSeverity.INFO
        )
        status = FlowtriqProvider.STATUS_MAP.get(
            raw_status.lower(), AlertStatus.FIRING
        )

        # Build a descriptive name
        title = incident.get("title")
        if title:
            name = title
        else:
            name = f"{attack_family} on {node_ip}"

        # Build description with attack metrics if available
        description_parts = []
        if incident.get("description"):
            description_parts.append(incident["description"])
        if incident.get("peak_bps"):
            bps = incident["peak_bps"]
            if bps >= 1_000_000_000:
                description_parts.append(f"Peak bandwidth: {bps / 1e9:.1f} Gbps")
            elif bps >= 1_000_000:
                description_parts.append(f"Peak bandwidth: {bps / 1e6:.1f} Mbps")
            else:
                description_parts.append(f"Peak bandwidth: {bps / 1e3:.1f} Kbps")
        if incident.get("peak_pps"):
            pps = incident["peak_pps"]
            if pps >= 1_000_000:
                description_parts.append(f"Peak packet rate: {pps / 1e6:.1f} Mpps")
            else:
                description_parts.append(f"Peak packet rate: {pps / 1e3:.1f} Kpps")

        description = ". ".join(description_parts) if description_parts else None

        # Build the fingerprint from incident id and target node IP
        fingerprint = f"flowtriq-{attack_id}-{node_ip}" if attack_id else None

        # Collect labels
        labels = {}
        if incident.get("attack_family"):
            labels["attack_family"] = incident["attack_family"]
        if node_ip != "unknown":
            labels["node_ip_address"] = node_ip
        if node_name:
            labels["node_name"] = node_name
        if incident.get("source_ip_count"):
            labels["source_ip_count"] = str(incident["source_ip_count"])

        alert = AlertDto(
            id=attack_id,
            name=name,
            status=status,
            severity=severity,
            description=description,
            lastReceived=(
                incident.get("resolved_at")
                or incident.get("started_at")
                or datetime.datetime.now(datetime.timezone.utc).isoformat()
            ),
            source=["flowtriq"],
            fingerprint=fingerprint,
            url=incident.get("dashboard_url"),
            labels=labels,
            # Extra fields passed through to AlertDto
            node_ip_address=node_ip,
            node_name=node_name,
            attack_family=incident.get("attack_family"),
            peak_bps=incident.get("peak_bps"),
            peak_pps=incident.get("peak_pps"),
            started_at=incident.get("started_at"),
            resolved_at=incident.get("resolved_at"),
        )

        return alert


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    api_url = os.environ.get("FLOWTRIQ_API_URL", "https://app.flowtriq.com")
    api_key = os.environ.get("FLOWTRIQ_API_KEY")
    assert api_key, "FLOWTRIQ_API_KEY environment variable is required"

    config = ProviderConfig(
        description="Flowtriq DDoS Detection Provider",
        authentication={
            "api_url": api_url,
            "api_key": api_key,
        },
    )

    provider = FlowtriqProvider(
        context_manager, provider_id="flowtriq-test", config=config
    )
    print("Provider initialized successfully")
