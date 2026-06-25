"""
Flowtriq Provider is a class that allows receiving DDoS attack alerts from Flowtriq
and querying the Flowtriq API for alert enrichment.
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
    """Receive DDoS attack alerts from Flowtriq and query the Flowtriq API."""

    webhook_description = ""
    webhook_template = ""
    webhook_markdown = """
To send DDoS attack alerts from Flowtriq to Keep, configure a webhook in your Flowtriq dashboard:

1. Log in to your Flowtriq dashboard.
2. Navigate to Settings > Integrations > Webhooks.
3. Click "Add Webhook".
4. Set the webhook URL to {keep_webhook_api_url}.
5. Add a header with key "X-API-KEY" and value {api_key}.
6. Select the alert events you want to forward (e.g. attack start, attack end).
7. Save the webhook configuration.
"""

    PROVIDER_DISPLAY_NAME = "Flowtriq"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="read_alerts",
            description="Read DDoS attack alerts from Flowtriq",
        ),
    ]

    FINGERPRINT_FIELDS = ["id", "target_ip"]

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

    # Map Flowtriq attack status to Keep alert status.
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
        """Validate that the API key has read access by hitting the alerts endpoint."""
        self.logger.info("Validating Flowtriq provider scopes")
        try:
            response = requests.get(
                url=f"{self.authentication_config.api_url}/api/v1/alerts",
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
        """Pull active alerts from the Flowtriq API."""
        self.logger.info("Fetching alerts from Flowtriq")
        try:
            response = requests.get(
                url=f"{self.authentication_config.api_url}/api/v1/alerts",
                headers=self._build_headers(),
                timeout=30,
            )
            response.raise_for_status()
            alerts_data = response.json()

            alerts = []
            for event in alerts_data.get("alerts", []):
                alerts.append(self._format_alert(event))
            return alerts

        except Exception as e:
            self.logger.exception("Failed to fetch alerts from Flowtriq")
            raise Exception(f"Failed to fetch alerts from Flowtriq: {e}")

    def _query(self, alert_id: str = "", **kwargs) -> dict:
        """
        Query Flowtriq API for alert details (enrichment).

        Args:
            alert_id: The Flowtriq alert/attack ID to look up.

        Returns:
            dict: Full alert details from Flowtriq.
        """
        if not alert_id:
            raise ValueError("alert_id is required for Flowtriq queries")

        self.logger.info("Querying Flowtriq alert", extra={"alert_id": alert_id})
        try:
            response = requests.get(
                url=f"{self.authentication_config.api_url}/api/v1/alerts/{alert_id}",
                headers=self._build_headers(),
                timeout=30,
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            self.logger.exception(
                "Failed to query Flowtriq alert", extra={"alert_id": alert_id}
            )
            raise Exception(f"Failed to query Flowtriq alert {alert_id}: {e}")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Flowtriq webhook event or API response into a Keep AlertDto.

        Flowtriq sends DDoS attack alerts with fields like:
        - id: unique attack identifier
        - target_ip: the IP under attack
        - attack_type: classification (e.g. UDP flood, SYN flood, DNS amplification)
        - severity: critical, high, warning, low, info
        - status: active, ongoing, mitigated, ended, resolved
        - bandwidth_bps: peak attack bandwidth in bits per second
        - packets_pps: peak attack packet rate
        - started_at: ISO timestamp of attack start
        - ended_at: ISO timestamp of attack end (if resolved)
        - description: human-readable summary
        - source_countries: list of top source countries
        """
        attack_id = event.get("id")
        target_ip = event.get("target_ip", "unknown")
        attack_type = event.get("attack_type", "DDoS Attack")
        raw_severity = event.get("severity", "info")
        raw_status = event.get("status", "active")

        severity = FlowtriqProvider.SEVERITIES_MAP.get(
            raw_severity.lower(), AlertSeverity.INFO
        )
        status = FlowtriqProvider.STATUS_MAP.get(
            raw_status.lower(), AlertStatus.FIRING
        )

        # Build a descriptive name
        name = f"{attack_type} on {target_ip}"

        # Build description with attack metrics if available
        description_parts = []
        if event.get("description"):
            description_parts.append(event["description"])
        if event.get("bandwidth_bps"):
            bps = event["bandwidth_bps"]
            if bps >= 1_000_000_000:
                description_parts.append(f"Peak bandwidth: {bps / 1e9:.1f} Gbps")
            elif bps >= 1_000_000:
                description_parts.append(f"Peak bandwidth: {bps / 1e6:.1f} Mbps")
            else:
                description_parts.append(f"Peak bandwidth: {bps / 1e3:.1f} Kbps")
        if event.get("packets_pps"):
            pps = event["packets_pps"]
            if pps >= 1_000_000:
                description_parts.append(f"Peak packet rate: {pps / 1e6:.1f} Mpps")
            else:
                description_parts.append(f"Peak packet rate: {pps / 1e3:.1f} Kpps")

        description = ". ".join(description_parts) if description_parts else None

        # Build the fingerprint from attack id and target
        fingerprint = f"flowtriq-{attack_id}-{target_ip}" if attack_id else None

        # Collect labels
        labels = {}
        if event.get("attack_type"):
            labels["attack_type"] = event["attack_type"]
        if event.get("target_ip"):
            labels["target_ip"] = event["target_ip"]
        if event.get("source_countries"):
            labels["source_countries"] = ", ".join(event["source_countries"])
        if event.get("target_port"):
            labels["target_port"] = str(event["target_port"])
        if event.get("protocol"):
            labels["protocol"] = event["protocol"]

        alert = AlertDto(
            id=attack_id,
            name=name,
            status=status,
            severity=severity,
            description=description,
            lastReceived=(
                event.get("ended_at")
                or event.get("updated_at")
                or event.get("started_at")
                or datetime.datetime.now(datetime.timezone.utc).isoformat()
            ),
            source=["flowtriq"],
            fingerprint=fingerprint,
            url=event.get("url"),
            labels=labels,
            # Extra fields passed through to AlertDto via **kwargs / extra attributes
            target_ip=target_ip,
            attack_type=event.get("attack_type"),
            bandwidth_bps=event.get("bandwidth_bps"),
            packets_pps=event.get("packets_pps"),
            started_at=event.get("started_at"),
            ended_at=event.get("ended_at"),
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
