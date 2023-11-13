"""
PrometheusProvider is a class that provides a way to read data from Prometheus.
"""

import dataclasses
import os
from datetime import datetime

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig


@pydantic.dataclasses.dataclass
class PrometheusProviderAuthConfig:
    url: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Prometheus server URL",
            "hint": "https://prometheus-us-central1.grafana.net/api/prom",
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

receivers:
- name: "keep"
  webhook_configs:
  - url: '{keep_webhook_api_url}'
    send_resolved: true
    http_config:
      basic_auth:
        username: api_key
        password: {api_key}"""

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
            auth=auth
            if self.authentication_config.username
            and self.authentication_config.password
            else None,
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
        if not response.ok:
            return []
        alerts_data = response.json().get("data", {})
        alert_dtos = self.format_alert(alerts_data)
        return alert_dtos

    @staticmethod
    def format_alert(event: dict) -> list[AlertDto]:
        # TODO: need to support more than 1 alert per event
        alert_dtos = []
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
            alert_dto = AlertDto(
                id=alert_id,
                name=alert_id,
                description=description,
                status=alert.pop("state", None) or alert.pop("status", None),
                lastReceived=datetime.now().isoformat(),
                environment=labels.pop("environment", "unknown"),
                severity=labels.get("severity", "info"),
                source=["prometheus"],
                labels=labels,
                annotations=annotations,  # annotations can be used either by alert.annotations.some_annotation or by alert.some_annotation
                payload=alert,
            )
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
