"""
Mimir provider for Keep.

Grafana Mimir is a scalable, highly available, multi-tenant time series
database for Prometheus metrics. It exposes a Prometheus-compatible API and
additionally supports multi-tenancy via the X-Scope-OrgID header.

This provider supports:
- Pull: fetches firing alerts from the Mimir Alertmanager/Ruler API
- Push: receives alerts from Mimir's Alertmanager webhook receiver

References:
- https://grafana.com/docs/mimir/latest/
- https://grafana.com/docs/mimir/latest/references/http-api/
"""

import dataclasses
import datetime
import uuid as uuid_module

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MimirProviderAuthConfig:
    """Authentication configuration for Mimir."""

    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Mimir server URL",
            "hint": "https://mimir.example.com or https://prometheus-blocks-prod-us-central1.grafana.net/api/prom",
            "validation": "any_http_url",
        }
    )
    org_id: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Mimir Org/Tenant ID (X-Scope-OrgID header)",
            "hint": "Required for multi-tenant Mimir deployments. Use 'anonymous' for single-tenant.",
            "sensitive": False,
        },
        default="anonymous",
    )
    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Basic auth username (for Grafana Cloud Mimir)",
            "sensitive": False,
        },
        default="",
    )
    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Basic auth password or Grafana Cloud API key",
            "sensitive": True,
        },
        default="",
    )
    verify: bool = dataclasses.field(
        metadata={
            "required": False,
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class MimirProvider(BaseProvider, ProviderHealthMixin):
    """Pull/receive alerts from Grafana Mimir into Keep."""

    PROVIDER_DISPLAY_NAME = "Mimir"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    FINGERPRINT_FIELDS = ["fingerprint"]

    webhook_description = "This provider takes advantage of Mimir Alertmanager's webhook receiver. Use the following template to configure it:"
    webhook_template = """route:
  receiver: "keep"
  group_by: ['alertname']
  group_wait:      15s
  group_interval:  15s
  repeat_interval: 1m
  continue: true

receivers:
- name: "keep"
  webhook_configs:
  - url: '{keep_webhook_api_url}'
    send_resolved: true
    http_config:
      basic_auth:
        username: api_key
        password: {api_key}"""

    SEVERITIES_MAP = {
        "critical": AlertSeverity.CRITICAL,
        "error": AlertSeverity.HIGH,
        "high": AlertSeverity.HIGH,
        "warning": AlertSeverity.WARNING,
        "medium": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity",
            description="Connectivity test — can reach the Mimir API",
            mandatory=True,
        )
    ]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = MimirProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self) -> dict:
        """Build request headers, including the multi-tenant org ID."""
        headers = {}
        org_id = getattr(self.authentication_config, "org_id", "anonymous")
        if org_id:
            headers["X-Scope-OrgID"] = org_id
        return headers

    def _get_auth(self):
        cfg = self.authentication_config
        if cfg.username and cfg.password:
            return HTTPBasicAuth(cfg.username, cfg.password)
        return None

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {"connectivity": True}
        try:
            self._get_alerts()
        except Exception as e:
            validated_scopes["connectivity"] = str(e)
        return validated_scopes

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull active alerts from the Mimir Ruler/Alertmanager API.

        Mimir exposes Prometheus-compatible alert endpoints:
        GET /prometheus/api/v1/alerts  — active firing alerts from the Ruler
        """
        response = requests.get(
            f"{self.authentication_config.url}/prometheus/api/v1/alerts",
            headers=self._get_headers(),
            auth=self._get_auth(),
            verify=self.authentication_config.verify,
            timeout=30,
        )
        response.raise_for_status()
        alerts_data = response.json().get("data", {})
        return MimirProvider._format_alert(alerts_data)

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format a Mimir alert payload into AlertDto objects.

        Accepts both:
        - The raw alerts list from GET /prometheus/api/v1/alerts (via _get_alerts)
        - Alertmanager webhook payloads (via Keep's webhook endpoint)

        The payload format is identical to Prometheus Alertmanager.
        """
        alert_dtos = []

        if isinstance(event, list):
            alerts = event
        else:
            alerts = event.get("alerts", [event])

        for alert in alerts:
            raw_id = alert.get("id")
            if raw_id:
                try:
                    uuid_module.UUID(str(raw_id))
                    alert_id = raw_id
                except (ValueError, AttributeError):
                    alert_id = str(uuid_module.uuid4())
            else:
                alert_name = alert.get("labels", {}).get("alertname")
                alert_id = alert_name if alert_name else str(uuid_module.uuid4())

            description = alert.get("annotations", {}).pop(
                "description", None
            ) or alert.get("annotations", {}).get("summary", alert_id)

            labels = {k.lower(): v for k, v in alert.pop("labels", {}).items()}
            annotations = {
                k.lower(): v for k, v in alert.pop("annotations", {}).items()
            }
            service = labels.get("service", annotations.get("service", None))

            status = alert.pop("state", None) or alert.pop("status", None)
            status = MimirProvider.STATUS_MAP.get(status, AlertStatus.FIRING)
            severity = MimirProvider.SEVERITIES_MAP.get(
                labels.get("severity"), AlertSeverity.INFO
            )

            alert_dto = AlertDto(
                id=alert_id,
                name=alert_id,
                description=description,
                status=status,
                service=service,
                lastReceived=datetime.datetime.now(
                    tz=datetime.timezone.utc
                ).isoformat(),
                environment=labels.pop("environment", "unknown"),
                severity=severity,
                source=["mimir"],
                labels=labels,
                annotations=annotations,
                payload=alert,
                fingerprint=alert.pop("fingerprint", None),
                **alert,
            )
            for label in labels:
                if getattr(alert_dto, label, None) is not None:
                    continue
                setattr(alert_dto, label, labels[label])
            for _field in ("value", "instance", "job"):
                if getattr(alert_dto, _field, None) is None:
                    setattr(alert_dto, _field, "")
            alert_dtos.append(alert_dto)

        return alert_dtos

    def dispose(self):
        pass
