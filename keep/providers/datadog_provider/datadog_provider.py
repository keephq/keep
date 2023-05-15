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
        initialize(
            api_key=self.authentication_config.api_key,
            app_key=self.authentication_config.app_key,
        )
        monitors = api.Monitor.get_all()
        return monitors

    def deploy_alert(self, alert: dict, alert_id: str | None = None):
        return api.Monitor.create(alert)

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
    alerts = provider.get_alerts()
    print(alerts)
