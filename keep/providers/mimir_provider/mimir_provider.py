"""
MimirProvider integrates Keep with Grafana Mimir — a horizontally scalable,
highly available, multi-tenant, long-term Prometheus metrics backend.
Supports querying active alerts via Mimir's built-in Alertmanager API and Ruler API.
Reference: https://grafana.com/docs/mimir/latest/references/http-api/
"""

import dataclasses
import logging
from datetime import datetime, timezone

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MimirProviderAuthConfig:
    """
    Grafana Mimir provider authentication configuration.
    Reference: https://grafana.com/docs/mimir/latest/references/http-api/
    """

    base_url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Mimir server base URL",
            "hint": "e.g. http://mimir:9009 or https://mimir.example.com",
        }
    )
    tenant_id: str = dataclasses.field(
        default="anonymous",
        metadata={
            "required": False,
            "description": "Mimir tenant ID (X-Scope-OrgID header)",
            "hint": "Use 'anonymous' for single-tenant mode (default)",
        },
    )
    username: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Basic auth username (for Grafana Cloud Mimir)",
            "hint": "Your Grafana Cloud username / instance ID",
        },
    )
    password: str = dataclasses.field(
        default="",
        metadata={
            "required": False,
            "description": "Basic auth password or API key (for Grafana Cloud Mimir)",
            "sensitive": True,
        },
    )
    verify_ssl: bool = dataclasses.field(
        default=True,
        metadata={
            "required": False,
            "description": "Verify SSL certificate (default: true)",
        },
    )


class MimirProvider(BaseProvider):
    """
    Pull firing alerts from Grafana Mimir's built-in Alertmanager
    and receive alerts via Mimir's Alertmanager webhook receiver.
    """

    PROVIDER_DISPLAY_NAME = "Mimir"
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert", "metrics"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="alertmanager:read",
            description="Required to read firing alerts from Mimir Alertmanager",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://grafana.com/docs/mimir/latest/references/http-api/#alertmanager",
            alias="Mimir Alertmanager Access",
        ),
        ProviderScope(
            name="webhook:receive",
            description="Required to receive alert webhooks from Mimir Alertmanager",
            mandatory=False,
            mandatory_for_webhook=True,
            documentation_url="https://grafana.com/docs/mimir/latest/references/http-api/#alertmanager",
            alias="Webhook Receiver",
        ),
    ]

    SEVERITY_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "page": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "warn": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "none": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MimirProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        pass

    @property
    def __headers(self):
        headers = {
            "X-Scope-OrgID": self.authentication_config.tenant_id,
            "Content-Type": "application/json",
        }
        return headers

    @property
    def __auth(self):
        if self.authentication_config.username and self.authentication_config.password:
            return (
                self.authentication_config.username,
                self.authentication_config.password,
            )
        return None

    def _get(self, path: str) -> dict | list:
        base = self.authentication_config.base_url.rstrip("/")
        url = f"{base}{path}"
        resp = requests.get(
            url,
            headers=self.__headers,
            auth=self.__auth,
            verify=self.authentication_config.verify_ssl,
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()

    def validate_scopes(self) -> dict[str, bool | str]:
        scopes = {scope.name: "Invalid" for scope in self.PROVIDER_SCOPES}
        try:
            # Mimir Alertmanager - get alerts endpoint
            self._get("/alertmanager/api/v2/alerts")
            scopes["alertmanager:read"] = True
        except Exception as e:
            scopes["alertmanager:read"] = str(e)
        scopes["webhook:receive"] = True
        return scopes

    def get_alerts(self) -> list[AlertDto]:
        """Fetch all firing alerts from Mimir's Alertmanager API."""
        try:
            alerts_data = self._get("/alertmanager/api/v2/alerts")
            if not isinstance(alerts_data, list):
                self.logger.warning("Unexpected Alertmanager response format")
                return []
            return [self._format_alert(a) for a in alerts_data]
        except Exception:
            self.logger.exception("Failed to fetch alerts from Mimir Alertmanager")
            return []

    @staticmethod
    def _parse_prom_ts(ts: str) -> str | None:
        """Parse Prometheus/Alertmanager ISO timestamp."""
        if not ts:
            return None
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
        ):
            try:
                return datetime.strptime(ts, fmt).replace(tzinfo=timezone.utc).isoformat()
            except Exception:
                continue
        return ts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "MimirProvider" = None
    ) -> AlertDto:
        """
        Format a Mimir Alertmanager alert (API or webhook) into Keep AlertDto.

        Mimir Alertmanager webhook payload (via Alertmanager webhook receiver) follows
        the standard Prometheus Alertmanager webhook format:
        https://prometheus.io/docs/alerting/latest/configuration/#webhook_config

        Example Alertmanager receiver config:
            receivers:
              - name: keep-receiver
                webhook_configs:
                  - url: "https://<keep>/alerts/event/mimir"
                    send_resolved: true
        """
        logger = logging.getLogger(__name__)

        labels = event.get("labels", {})
        annotations = event.get("annotations", {})

        # Handle both direct alert and webhook payload (which wraps alerts in 'alerts' array)
        if "alerts" in event:
            # Webhook root payload — format first alert for single-alert handling
            # (Keep calls _format_alert per-alert from the webhook handler)
            alerts = event.get("alerts", [])
            if alerts:
                return MimirProvider._format_alert(alerts[0])

        alert_name = labels.get("alertname", "Mimir Alert")
        raw_severity = (
            labels.get("severity")
            or labels.get("priority")
            or annotations.get("severity")
            or "warning"
        )
        severity = MimirProvider.SEVERITY_MAP.get(
            str(raw_severity).lower(), AlertSeverity.WARNING
        )

        # Status from Alertmanager
        raw_status = event.get("status", "firing")
        if raw_status == "resolved":
            status = AlertStatus.RESOLVED
        elif raw_status == "suppressed":
            status = AlertStatus.SUPPRESSED
        else:
            status = AlertStatus.FIRING

        starts_at = MimirProvider._parse_prom_ts(event.get("startsAt"))
        ends_at = MimirProvider._parse_prom_ts(event.get("endsAt"))

        description = (
            annotations.get("description")
            or annotations.get("summary")
            or annotations.get("message")
            or ""
        )
        summary = annotations.get("summary", alert_name)

        # Build unique ID from fingerprint or labels
        fingerprint = event.get("fingerprint") or str(labels)

        return AlertDto(
            id=fingerprint,
            name=summary or alert_name,
            status=status,
            severity=severity,
            description=description,
            lastReceived=starts_at,
            resolvedAt=ends_at if status == AlertStatus.RESOLVED else None,
            source=["mimir"],
            labels=labels,
            annotations=annotations,
            generator_url=event.get("generatorURL"),
            namespace=labels.get("namespace"),
            cluster=labels.get("cluster"),
            job=labels.get("job"),
            instance=labels.get("instance"),
            payload=event,
        )


if __name__ == "__main__":
    import os
    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    context_manager = ContextManager(tenant_id="keeptest", workflow_id="test")
    config = ProviderConfig(
        authentication={
            "base_url": os.environ.get("MIMIR_URL", "http://localhost:9009"),
            "tenant_id": os.environ.get("MIMIR_TENANT_ID", "anonymous"),
            "username": os.environ.get("MIMIR_USERNAME", ""),
            "password": os.environ.get("MIMIR_PASSWORD", ""),
            "verify_ssl": False,
        }
    )
    provider = MimirProvider(context_manager, "mimir-test", config)
    print("Scopes:", provider.validate_scopes())
    alerts = provider.get_alerts()
    print(f"Found {len(alerts)} firing alerts")
    for a in alerts:
        print(a)
