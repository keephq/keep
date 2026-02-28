"""
Nagios Provider is a class that allows to ingest/digest data from Nagios.
"""

import dataclasses
import datetime
import json
import logging
import os
import random
from typing import Union

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.base.provider_exceptions import ProviderMethodException
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios URL",
            "hint": "https://nagios.example.com/nagios",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios API Key",
            "hint": "Nagios XI API Key",
            "sensitive": True,
        }
    )
    verify: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false to allow self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class NagiosProvider(BaseProvider):
    """
    Pull/Push alerts from Nagios into Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_TAGS = ["alert"]

    SEVERITIES_MAP = {
        "OK": AlertSeverity.INFO,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.LOW,
    }

    STATUS_MAP = {
        "0": AlertStatus.RESOLVED,  # OK
        "1": AlertStatus.FIRING,    # WARNING
        "2": AlertStatus.FIRING,    # CRITICAL
        "3": AlertStatus.LOW,       # UNKNOWN
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def validate_config(self):
        """
        Validates required configuration for Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def _get_alerts(self) -> list[AlertDto]:
        # Using Nagios XI API to get objects
        # https://assets.nagios.com/downloads/nagiosxi/docs/Ondoc/API/
        url = f"{self.authentication_config.nagios_url}/api/v1/objects/servicestatus"
        params = {
            "apikey": self.authentication_config.api_key,
        }
        response = requests.get(
            url, params=params, verify=self.authentication_config.verify
        )
        response.raise_for_status()
        data = response.json()

        formatted_alerts = []
        # Handle the structure of Nagios XI API response
        service_statuses = data.get("servicestatus", [])
        if not isinstance(service_statuses, list):
            service_statuses = [service_statuses]

        for status in service_statuses:
            # Nagios XI status: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
            current_state = status.get("current_state", "3")
            state_text = "UNKNOWN"
            if current_state == "0": state_text = "OK"
            elif current_state == "1": state_text = "WARNING"
            elif current_state == "2": state_text = "CRITICAL"

            # Filter only problematic statuses if needed, but Keep usually pulls all
            formatted_alerts.append(
                AlertDto(
                    id=f"{status.get('host_name')}-{status.get('service_description')}",
                    name=status.get("service_description", "Unknown Service"),
                    status=self.STATUS_MAP.get(current_state, AlertStatus.FIRING),
                    lastReceived=status.get("last_check", datetime.datetime.now(tz=datetime.timezone.utc).isoformat()),
                    source=["nagios"],
                    message=status.get("status_text", ""),
                    severity=self.SEVERITIES_MAP.get(state_text, AlertSeverity.INFO),
                    environment="unknown",
                    service=status.get("host_name"),
                    hostname=status.get("host_name"),
                )
            )
        return formatted_alerts

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        # Standard format for Nagios alerts coming from webhooks/scripts
        return AlertDto(
            id=event.get("id", str(random.randint(1000, 2000))),
            name=event.get("service", "Nagios Alert"),
            status=AlertStatus.FIRING if event.get("state") != "OK" else AlertStatus.RESOLVED,
            lastReceived=datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
            source=["nagios"],
            message=event.get("output", ""),
            severity=NagiosProvider.SEVERITIES_MAP.get(event.get("state"), AlertSeverity.INFO),
            environment=event.get("environment", "unknown"),
            hostname=event.get("host"),
            service=event.get("service"),
        )


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    # Load environment variables
    import os

    api_key = os.environ.get("NAGIOS_API_KEY")

    provider_config = {
        "authentication": {
            "api_key": api_key,
            "nagios_url": "http://localhost/nagiosxi",
        },
    }
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="nagios",
        provider_type="nagios",
        provider_config=provider_config,
    )
    alerts = provider.get_alerts()
    print(alerts)
