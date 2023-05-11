"""
Grafana Provider is a class that allows to ingest/digest data from Grafana.
"""

import pydantic
import requests
from grafana_api.alerting import Alerting
from grafana_api.alerting_provisioning import AlertingProvisioning
from grafana_api.model import APIEndpoints, APIModel

from keep.providers.base.base_provider import BaseProvider
from keep.providers.grafana_provider.grafana_alert_format_description import (
    GrafanaAlertFormatDescription,
)
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class GrafanaAuthConfig:
    """
    Grafana authentication configuration.
    """

    host: str
    token: str


class GrafanaProvider(BaseProvider):
    """
    Grafana provider class.
    """

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Grafana provider.

        """
        self.authentication_config = GrafanaAuthConfig(**self.config.authentication)

    def query(self, **kwargs: dict):
        pass

    def get_alerts(self, alert_id: str | None = None):
        api_model = APIModel(
            host=self.authentication_config.host, token=self.authentication_config.token
        )
        alerting_sdk = Alerting(api_model)
        alerts_list = alerting_sdk.get_alertmanager_alerts()
        alerts_definitions = []
        provisioner = AlertingProvisioning(api_model)
        for alert in alerts_list:
            alert_uid = alert.get("labels", {}).get("__alert_rule_uid__")
            alerts_definitions.append(provisioner.get_alert_rule(alert_uid))
        return alerts_definitions

    def deploy_alert(self, alert: dict, alert_id: str | None = None):
        self.logger.info("Deploying alert")
        api = f"{self.authentication_config.host}{APIEndpoints.ALERTING_PROVISIONING.value}/alert-rules"
        headers = {"Authorization": f"Bearer {self.authentication_config.token}"}
        response = requests.post(api, json=alert, headers=headers)
        self.logger.info(
            "Alert deployed",
            extra={"status": response.status_code, "data": response.json()},
        )
        return {"status": response.status_code, "data": response.json()}

    @staticmethod
    def get_alert_format_description():
        return GrafanaAlertFormatDescription.schema_json()


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    host = os.environ.get("GRAFANA_HOST")
    token = os.environ.get("GRAFANA_TOKEN")

    config = {
        "authentication": {"host": host, "token": token},
    }
    provider = ProvidersFactory.get_provider(
        provider_id="grafana-keephq", provider_type="grafana", provider_config=config
    )
    alerts = provider.get_alerts()
    print(alerts)
