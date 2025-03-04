"""
ThousandEyes is a class that implements the BaseProvider interface for ThousandEyes monitoring.
"""

import dataclasses
import datetime
from typing import List, Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory


@pydantic.dataclasses.dataclass
class ThousandEyesProviderAuthConfig:
    """
    ThousandEyes authentication configuration.
    """

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "ThousandEyes API Token",
            "sensitive": True,
        }
    )


class ThousandEyesProvider(BaseProvider):
    """
    ThousandEyes provider for Keep.
    """

    PROVIDER_DISPLAY_NAME = "ThousandEyes"
    PROVIDER_TAGS = ["monitoring", "network"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="read",
            description="Read alerts from ThousandEyes.",
            mandatory=True,
        ),
    ]
    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "HIGH": AlertSeverity.HIGH,
        "MEDIUM": AlertSeverity.WARNING,
        "LOW": AlertSeverity.LOW,
    }
    STATUS_MAP = {
        "ACTIVE": AlertStatus.FIRING,
        "RESOLVED": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.api_url = "https://api.thousandeyes.com/v6"

    def validate_config(self):
        """
        Validate provider configuration.
        """
        self.authentication_config = ThousandEyesProviderAuthConfig(
            **self.config.authentication
        )

    def _get_headers(self):
        """
        Get headers for ThousandEyes API requests.
        """
        return {
            "Authorization": f"Bearer {self.authentication_config.api_token}",
            "Content-Type": "application/json",
        }

    def _get_alerts(self) -> List[AlertDto]:
        """
        Retrieve alerts from ThousandEyes.
        """
        try:
            url = f"{self.api_url}/alerts"
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            alerts = response.json().get("alerts", [])

            formatted_alerts = []
            for alert in alerts:
                formatted_alerts.append(
                    AlertDto(
                        id=alert.get("alertId"),
                        name=alert.get("testName"),
                        status=self.STATUS_MAP.get(
                            alert.get("status"), AlertStatus.FIRING
                        ),
                        severity=self.SEVERITIES_MAP.get(
                            alert.get("severity"), AlertSeverity.INFO
                        ),
                        lastReceived=datetime.datetime.now().isoformat(),
                        description=alert.get("message"),
                        source=["thousandeyes"],
                    )
                )
            return formatted_alerts
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Failed to fetch alerts from ThousandEyes: {e}")
            raise

    def _format_alert(self, event: dict) -> AlertDto:
        """
        Format an incoming alert from ThousandEyes into Keep's alert model.

        Args:
            event (dict): The raw alert data received from ThousandEyes.

        Returns:
            AlertDto: The formatted alert in Keep's standard format.
        """
        return AlertDto(
            id=event.get("alertId"),
            name=event.get("testName"),
            status=self.STATUS_MAP.get(event.get("status"), AlertStatus.FIRING),
            severity=self.SEVERITIES_MAP.get(event.get("severity"), AlertSeverity.INFO),
            lastReceived=datetime.datetime.now().isoformat(),
            description=event.get("message"),
            source=["thousandeyes"],
        )

    def handle_webhook(self, request: dict) -> List[AlertDto]:
        """
        Handle incoming webhook events from ThousandEyes.

        Args:
            request (dict): The webhook payload received from ThousandEyes.

        Returns:
            List[AlertDto]: A list of formatted alerts.
        """
        alerts = []
        for event in request.get("alerts", []):
            formatted_alert = self._format_alert(event)
            alerts.append(formatted_alert)
        return alerts

    def notify(self, alert: AlertDto):
        """
        Send a notification using ThousandEyes.
        """
        # Implement notification logic if needed.
        pass


if __name__ == "__main__":
    # Output debug messages
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])

    # Load environment variables
    import os

    api_token = os.environ.get("THOUSANDEYES_API_TOKEN")
    if not api_token:
        raise Exception("THOUSANDEYES_API_TOKEN environment variable is not set")

    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )
    config = {"authentication": {"api_token": api_token}}
    provider = ProvidersFactory.get_provider(
        context_manager,
        provider_id="thousandeyes-keephq",
        provider_type="thousandeyes",
        provider_config=config,
    )
    alerts = provider.get_alerts()
    print(alerts)