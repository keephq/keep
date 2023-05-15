"""
Datadog Provider is a class that allows to ingest/digest data from Datadog.
"""

import pydantic
from datadog import api, initialize

from keep.providers.base.base_provider import BaseProvider
from keep.providers.datadog_provider.datadog_alert_format_description import (
    DatadogAlertFormatDescription,
)
from keep.providers.models.provider_config import ProviderConfig
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class DatadogAuthConfig:
    """
    Datadog authentication configuration.
    """

    api_key: str
    app_key: str


class DatadogProvider(BaseProvider):
    """
    Datadog provider class.
    """

    def __init__(self, provider_id: str, config: ProviderConfig):
        super().__init__(provider_id, config)
        initialize(
            api_key=self.authentication_config.api_key,
            app_key=self.authentication_config.app_key,
        )

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Datadog provider.

        """
        self.authentication_config = DatadogAuthConfig(**self.config.authentication)

    def query(self, **kwargs: dict):
        pass

    def get_alerts(self, alert_id: str | None = None):
        monitors = api.Monitor.get_all()
        return monitors

    def deploy_alert(self, alert: dict, alert_id: str | None = None):
        created_alert = api.Monitor.create(**alert)
        return created_alert

    @staticmethod
    def get_alert_format_description():
        return DatadogAlertFormatDescription.schema()


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    api_key = os.environ.get("DATADOG_API_KEY")
    app_key = os.environ.get("DATADOG_APP_KEY")

    config = {
        "authentication": {"api_key": api_key, "app_key": app_key},
    }
    provider = ProvidersFactory.get_provider(
        provider_id="datadog-keephq", provider_type="datadog", provider_config=config
    )
    alerts = provider.deploy_alert(
        {
            "name": "Error Rate Alert",
            "type": "metric alert",
            "query": "sum:myapp.server.errors{service:talboren/simple-crud-service}.as_count().rollup(sum, 600)",
            "message": "The error rate for talboren/simple-crud-service has exceeded 5% in the last 10 minutes. Please investigate immediately",
            "tags": ["service:talboren/simple-crud-service", "severity:critical"],
            "options": {
                "thresholds": {"critical": 5},
                "notify_audit": False,
                "notify_no_data": False,
                "require_full_window": True,
                "timeout_h": 1,
                "silenced": {},
            },
            "restricted_roles": [],
            "priority": 2,
        }
    )
    print(alerts)
