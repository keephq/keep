"""
PrometheusProvider is a class that provides a way to read data from Prometheus.
"""

import dataclasses
import os

import pydantic
import requests
from requests.auth import HTTPBasicAuth

from keep.api.models.alert import AlertDto
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
        metadata={"description": "Prometheus username"},
    )
    password: str = dataclasses.field(
        metadata={
            "description": "Prometheus password",
            "sensitive": True,
        },
    )


class PrometheusProvider(BaseProvider):
    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

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

        response = requests.get(
            f"{self.authentication_config.url}/api/v1/query",
            params={"query": query},
            auth=HTTPBasicAuth(
                self.authentication_config.username, self.authentication_config.password
            )
            if self.authentication_config.username
            and self.authentication_config.password
            else None,
        )

        if response.status_code != 200:
            raise Exception(f"Prometheus query failed: {response.content}")

        return response.json()

    def get_alerts(self) -> list[AlertDto]:
        response = requests.get(
            f"{self.authentication_config.url}/api/v1/alerts",
            auth=HTTPBasicAuth(
                self.authentication_config.username, self.authentication_config.password
            ),
        )
        if not response.ok:
            return []
        alerts = response.json().get("data", {}).get("alerts", [])
        alert_dtos = []
        for alert in alerts:
            alert_dto = self.format_alert(alert)
            alert_dtos.append(alert_dto)
        return alert_dtos

    @staticmethod
    def format_alert(event: dict) -> AlertDto:
        alert_id = event.get("id", event.get("labels", {}).get("alertname"))
        description = event.get("annotations", {}).pop(
            "description", None
        ) or event.get("annotations", {}).get("summary", alert_id)

        labels = {k.lower(): v for k, v in event.get("labels", {}).items()}
        annotations = {k.lower(): v for k, v in event.get("annotations", {}).items()}
        alert_dto = AlertDto(
            id=alert_id,
            name=alert_id,
            description=description,
            status=event.get("state"),
            lastReceived=event.get("activeAt"),
            source=["prometheus"],
            **labels,
            **annotations,
        )
        return alert_dto

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
    prometheus_provider = PrometheusProvider("prometheus-prod", config)
    results = prometheus_provider.query(
        query="sum by (job) (rate(prometheus_http_requests_total[5m]))"
    )
    results = prometheus_provider.query(
        query='Number_of_webhooks{name="Number of webhooks"}'
    )
    print(results)
