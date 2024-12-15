"""
PrometheusProvider is a class that provides a way to read data from Prometheus.
"""

import dataclasses
import datetime
import os

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class PrometheusProviderAuthConfig:
    url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Prometheus server URL",
            "hint": "https://prometheus-us-central1.grafana.net/api/prom",
            "validation": "any_http_url"
        }
    )
    username: str = dataclasses.field(
        metadata={
            "description": "Prometheus username",
            "sensitive": False,
        },
        default="",
    )
    password: str = dataclasses.field(
        metadata={
            "description": "Prometheus password",
            "sensitive": True,
        },
        default="",
    )


class PrometheusProvider(BaseProvider):
    """Get alerts from Prometheus into Keep."""

    webhook_description = "This provider takes advantage of configurable webhooks available with Prometheus Alertmanager. Use the following template to configure AlertManager:"
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
        "warning": AlertSeverity.WARNING,
        "info": AlertSeverity.INFO,
        "low": AlertSeverity.LOW,
    }
    PROVIDER_CATEGORY = ["Monitoring"]

    STATUS_MAP = {
        "firing": AlertStatus.FIRING,
        "resolved": AlertStatus.RESOLVED,
    }

    PROVIDER_SCOPES = [
        ProviderScope(
            name="connectivity", description="Connectivity Test", mandatory=True
        )
    ]
    FINGERPRINT_FIELDS = ["fingerprint"]

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Prometheus's provider.
        """
        self.authentication_config = PrometheusProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        validated_scopes = {"connectivity": True}
        try:
            self._get_alerts()
        except Exception as e:
            validated_scopes["connectivity"] = str(e)
        return validated_scopes

    def _query(self, query):
        """
        Executes a query against the Prometheus server.

        Returns:
            list | tuple: list of results or single result if single_row is True
        """
        if not query:
            raise ValueError("Query is required")

        auth = None
        if self.authentication_config.username and self.authentication_config.password:
            auth = HTTPBasicAuth(
                self.authentication_config.username, self.authentication_config.password
            )

        response = requests.get(
            f"{self.authentication_config.url}/api/v1/query",
            params={"query": query},
            auth=(
                auth
                if self.authentication_config.username
                and self.authentication_config.password
                else None
            ),
        )

        if response.status_code != 200:
            raise Exception(f"Prometheus query failed: {response.content}")

        return response.json()

    def _get_alerts(self) -> list[AlertDto]:
        auth = None
        if self.authentication_config.username and self.authentication_config.password:
            auth = HTTPBasicAuth(
                self.authentication_config.username, self.authentication_config.password
            )
        response = requests.get(
            f"{self.authentication_config.url}/api/v1/alerts",
            auth=auth,
        )
        response.raise_for_status()
        if not response.ok:
            return []
        alerts_data = response.json().get("data", {})
        alert_dtos = self._format_alert(alerts_data)
        return alert_dtos

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> list[AlertDto]:
        # TODO: need to support more than 1 alert per event
        alert_dtos = []
        if isinstance(event, list):
            return event
        else:
            alerts = event.get("alerts", [event])

        for alert in alerts:
            alert_id = alert.get("id", alert.get("labels", {}).get("alertname"))
            description = alert.get("annotations", {}).pop(
                "description", None
            ) or alert.get("annotations", {}).get("summary", alert_id)

            labels = {k.lower(): v for k, v in alert.pop("labels", {}).items()}
            annotations = {
                k.lower(): v for k, v in alert.pop("annotations", {}).items()
            }
            service = labels.get("service", annotations.get("service", None))
            # map severity and status to keep's format
            status = alert.pop("state", None) or alert.pop("status", None)
            status = PrometheusProvider.STATUS_MAP.get(status, AlertStatus.FIRING)
            severity = PrometheusProvider.SEVERITIES_MAP.get(
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
                source=["prometheus"],
                labels=labels,
                annotations=annotations,  # annotations can be used either by alert.annotations.some_annotation or by alert.some_annotation
                payload=alert,
                fingerprint=alert.pop("fingerprint", None),
                **alert,  # rest of the fields
            )
            for label in labels:
                if getattr(alert_dto, label, None) is not None:
                    continue
                setattr(alert_dto, label, labels[label])
            alert_dtos.append(alert_dto)
        return alert_dtos

    def dispose(self):
        """
        Disposes of the Prometheus provider.
        """
        return

    def notify(self, **kwargs):
        """
        Notifies the Prometheus server.
        """
        raise NotImplementedError("Prometheus provider does not support notify()")

    @classmethod
    def simulate_alert(cls, **kwargs) -> dict:
        """Mock a Prometheus alert."""
        import hashlib
        import json
        import random

        from keep.providers.prometheus_provider.alerts_mock import ALERTS

        alert_type = kwargs.get("alert_type")
        if not alert_type:
            alert_type = random.choice(list(ALERTS.keys()))

        to_wrap_with_provider_type = kwargs.get("to_wrap_with_provider_type")

        alert_payload = ALERTS[alert_type]["payload"]
        alert_parameters = ALERTS[alert_type].get("parameters", [])
        # now generate some random data
        for parameter, parameter_options in alert_parameters.items():
            # choose random param

            # support "labels.some_label" format
            if "." in parameter:
                # nested parameter
                parameter = parameter.split(".")
                if parameter[0] not in alert_payload:
                    alert_payload[parameter[0]] = {}
                alert_payload[parameter[0]][parameter[1]] = random.choice(
                    parameter_options
                )
            else:
                alert_payload[parameter] = random.choice(parameter_options)
        annotations = {"summary": alert_payload["summary"]}
        alert_payload["labels"]["alertname"] = alert_type
        alert_payload["status"] = random.choice(
            [AlertStatus.FIRING.value, AlertStatus.RESOLVED.value]
        )
        alert_payload["annotations"] = annotations
        alert_payload["startsAt"] = datetime.datetime.now(
            tz=datetime.timezone.utc
        ).isoformat()
        alert_payload["endsAt"] = "0001-01-01T00:00:00Z"
        alert_payload["generatorURL"] = "http://example.com/graph?g0.expr={}".format(
            alert_type
        )
        # TODO: use BaseProvider's get_alert_fingerprint
        fingerprint_src = json.dumps(alert_payload["labels"], sort_keys=True)
        fingerprint = hashlib.md5(fingerprint_src.encode()).hexdigest()
        alert_payload["fingerprint"] = fingerprint
        if to_wrap_with_provider_type:
            return {"source_type": "prometheus", "event": alert_payload}

        return alert_payload


if __name__ == "__main__":
    config = ProviderConfig(
        authentication={
            "url": os.environ.get("PROMETHEUS_URL"),
            "username": os.environ.get("PROMETHEUS_USER"),
            "password": os.environ.get("PROMETHEUS_PASSWORD"),
        }
    )
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    prometheus_provider = PrometheusProvider(context_manager, "prometheus-prod", config)
    results = prometheus_provider.query(
        query="sum by (job) (rate(prometheus_http_requests_total[5m]))"
    )
    results = prometheus_provider.query(
        query='Number_of_webhooks{name="Number of webhooks"}'
    )
    print(results)
