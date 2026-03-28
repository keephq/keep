"""
MimirProvider is a class that allows reading alerts and metrics from Grafana Mimir.

Mimir is a horizontally scalable, highly available, multi-tenant, long-term storage
for Prometheus metrics. It exposes the same API as Prometheus but adds multi-tenancy
support via the X-Scope-OrgID header and Alertmanager-compatible webhook support.

References:
  - https://grafana.com/docs/mimir/latest/operators-guide/reference-http-api/
  - https://grafana.com/docs/mimir/latest/manage/secure/authentication-and-authorization/
"""

import dataclasses
import datetime
import os

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider, ProviderHealthMixin
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class MimirProviderAuthConfig:
    """
    Mimir authentication configuration.

    Mimir supports both basic-auth (username/password) and API-key based auth.
    Multi-tenancy is controlled via the X-Scope-OrgID header (tenant field).
    """

    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Mimir server URL",
            "hint": "https://mimir.example.com or https://prometheus-us-central1.grafana.net/api/prom",
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "description": "Mimir username (for basic auth)",
            "hint": "Leave empty if not using basic auth",
            "sensitive": False,
        },
        default="",
    )
    password: str = dataclasses.field(
        metadata={
            "description": "Mimir password or API key",
            "hint": "Leave empty if not using basic auth",
            "sensitive": True,
        },
        default="",
    )
    tenant: str = dataclasses.field(
        metadata={
            "description": "Mimir tenant ID (X-Scope-OrgID header)",
            "hint": "Required for multi-tenant Mimir deployments. Leave empty for single-tenant.",
            "sensitive": False,
        },
        default="",
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class MimirProvider(BaseProvider, ProviderHealthMixin):
    """Get alerts from Grafana Mimir into Keep.

    Mimir exposes a Prometheus-compatible API, so this provider mirrors the
    Prometheus provider but adds:
      - X-Scope-OrgID multi-tenant header support
      - Mimir-specific Alertmanager webhook configuration template
    """

    # Alertmanager webhook template for Mimir
    webhook_description = (
        "Mimir supports Prometheus-compatible Alertmanager. "
        "Use the following template to configure your Mimir Alertmanager:"
    )
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

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "Grafana Mimir"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity",
            description="Connectivity test — verifies the Mimir endpoint is reachable.",
            mandatory=True,
        )
    ]

    FINGERPRINT_FIELDS = ["fingerprint"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """Validates required configuration for the Mimir provider."""
        self.authentication_config = MimirProviderAuthConfig(
            **self.config.authentication
        )

    def _get_auth(self):
        """Returns HTTPBasicAuth if credentials are configured, else None."""
        if (
            self.authentication_config.username
            and self.authentication_config.password
        ):
            return HTTPBasicAuth(
                self.authentication_config.username,
                self.authentication_config.password,
            )
        return None

    def _get_headers(self) -> dict:
        """Returns headers including the multi-tenant X-Scope-OrgID when configured."""
        headers = {}
        if self.authentication_config.tenant:
            headers["X-Scope-OrgID"] = self.authentication_config.tenant
        return headers

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validates connectivity to the Mimir endpoint."""
        validated_scopes = {"connectivity": True}
        try:
            self._get_alerts()
        except Exception as e:
            validated_scopes["connectivity"] = str(e)
        return validated_scopes

    def _query(self, query: str) -> dict:
        """
        Executes an instant PromQL query against Mimir.

        Args:
            query: PromQL query string.

        Returns:
            Raw Mimir API JSON response dict.

        Raises:
            ValueError: if the query string is empty.
            Exception: if the HTTP request fails.
        """
        if not query:
            raise ValueError("Query is required")

        response = requests.get(
            f"{self.authentication_config.url}/api/v1/query",
            params={"query": query},
            auth=self._get_auth(),
            headers=self._get_headers(),
            verify=self.authentication_config.verify,
        )
        if response.status_code != 200:
            raise Exception(f"Mimir query failed: {response.content}")

        return response.json()

    def _get_alerts(self) -> list[AlertDto]:
        """Fetches active Alertmanager alerts from Mimir."""
        response = requests.get(
            f"{self.authentication_config.url}/api/v1/alerts",
            auth=self._get_auth(),
            headers=self._get_headers(),
            verify=self.authentication_config.verify,
        )
        response.raise_for_status()
        if not response.ok:
            return []

        alerts_data = response.json().get("data", {})
        return self._format_alert(alerts_data)

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> list[AlertDto]:
        """Converts a raw Mimir/Alertmanager event payload into Keep AlertDto objects.

        Mimir uses the same Alertmanager wire format as Prometheus:
          {
            "version": "4",
            "groupKey": "...",
            "status": "firing|resolved",
            "alerts": [
              {
                "status": "firing|resolved",
                "labels": { "alertname": "...", "severity": "...", ... },
                "annotations": { "summary": "...", "description": "...", ... },
                "startsAt": "...",
                "endsAt": "...",
                "fingerprint": "...",
              }
            ]
          }
        """
        alert_dtos = []

        if isinstance(event, list):
            # Already a list of AlertDto — return as-is (from _get_alerts)
            return event

        alerts = event.get("alerts", [event])

        for alert in alerts:
            alert_id = alert.get("id") or alert.get("labels", {}).get("alertname")

            description = alert.get("annotations", {}).pop(
                "description", None
            ) or alert.get("annotations", {}).get("summary", alert_id)

            labels = {k.lower(): v for k, v in alert.pop("labels", {}).items()}
            annotations = {
                k.lower(): v for k, v in alert.pop("annotations", {}).items()
            }

            service = labels.get("service", annotations.get("service", None))

            status_raw = alert.pop("state", None) or alert.pop("status", None)
            status = MimirProvider.STATUS_MAP.get(status_raw, AlertStatus.FIRING)

            severity_raw = labels.get("severity", "")
            severity = MimirProvider.SEVERITIES_MAP.get(
                severity_raw.lower() if severity_raw else "", AlertSeverity.INFO
            )

            alert_dto = AlertDto(
                id=alert_id,
                name=alert_id,
                description=description,
                severity=severity,
                status=status,
                source=["mimir"],
                labels=labels,
                annotations=annotations,
                service=service,
                fingerprint=alert.get("fingerprint"),
                startedAt=alert.get("startsAt"),
                lastReceived=alert.get("startsAt"),
            )

            # Promote any remaining label keys onto the DTO
            for label_key, label_val in labels.items():
                if getattr(alert_dto, label_key, None) is None:
                    setattr(alert_dto, label_key, label_val)

            # Ensure workflow templates can reference these without safe=True errors
            for _field in ("value", "instance", "job"):
                if getattr(alert_dto, _field, None) is None:
                    setattr(alert_dto, _field, "")

            alert_dtos.append(alert_dto)

        return alert_dtos

    def dispose(self):
        """Disposes of the Mimir provider."""
        pass

    def notify(self, **kwargs):
        """Mimir is a read-only metrics source; notify() is not supported."""
        raise NotImplementedError("Mimir provider does not support notify()")

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        """Returns a mock Mimir/Alertmanager alert payload for testing."""
        import hashlib
        import json
        import random

        from keep.providers.mimir_provider.alerts_mock import ALERTS

        alert_type = kwargs.get("alert_type") or random.choice(list(ALERTS.keys()))
        to_wrap_with_provider_type = kwargs.get("to_wrap_with_provider_type")

        alert_payload = ALERTS[alert_type]["payload"].copy()
        alert_parameters = ALERTS[alert_type].get("parameters", {})

        for parameter, options in alert_parameters.items():
            if "." in parameter:
                parts = parameter.split(".", 1)
                if parts[0] not in alert_payload:
                    alert_payload[parts[0]] = {}
                alert_payload[parts[0]][parts[1]] = random.choice(options)
            else:
                alert_payload[parameter] = random.choice(options)

        alert_payload["labels"]["alertname"] = alert_type
        alert_payload["status"] = random.choice(
            [AlertStatus.FIRING.value, AlertStatus.RESOLVED.value]
        )
        alert_payload["annotations"] = {"summary": alert_payload.get("summary", alert_type)}
        alert_payload["startsAt"] = datetime.datetime.now(
            tz=datetime.timezone.utc
        ).isoformat()
        alert_payload["endsAt"] = "0001-01-01T00:00:00Z"
        alert_payload["generatorURL"] = (
            f"http://example.com/graph?g0.expr={alert_type}"
        )

        fingerprint_src = json.dumps(alert_payload["labels"], sort_keys=True)
        alert_payload["fingerprint"] = hashlib.md5(
            fingerprint_src.encode()
        ).hexdigest()

        if to_wrap_with_provider_type:
            return {"keep_source_type": "mimir", "event": alert_payload}

        return alert_payload


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "url": os.environ["MIMIR_URL"],
            "username": os.environ.get("MIMIR_USERNAME") or "",
            "password": os.environ.get("MIMIR_PASSWORD") or "",
            "tenant": os.environ.get("MIMIR_TENANT") or "",
            "verify": (os.environ.get("MIMIR_VERIFY") or "true").lower() == "true",
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    mimir_provider = MimirProvider(context_manager, "mimir-prod", config)
    results = mimir_provider._query(
        query="sum by (job) (rate(prometheus_http_requests_total[5m]))"
    )
    print(results)
