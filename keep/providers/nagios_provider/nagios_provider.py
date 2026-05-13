"""
NagiosProvider is a class that implements the BaseProvider interface for Nagios monitoring.
Supports both Nagios XI API and standard Nagios webhooks.
"""

import dataclasses
import datetime
import logging

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """Nagios authentication configuration."""

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL (e.g. http://nagios.example.com)",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios XI API Key (Required for Pulling alerts)",
            "sensitive": True,
        },
        default=None,
    )


class NagiosProvider(BaseProvider):
    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated", description="User is authenticated via API Key"
        ),
    ]

    # Nagios state to Keep status mapping
    # 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    STATUS_MAP = {
        "0": AlertStatus.RESOLVED,
        "1": AlertStatus.FIRING,
        "2": AlertStatus.FIRING,
        "3": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.FIRING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        "0": AlertSeverity.LOW,
        "1": AlertSeverity.WARNING,
        "2": AlertSeverity.CRITICAL,
        "3": AlertSeverity.INFO,
        "OK": AlertSeverity.LOW,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def _get_alerts(self) -> list[AlertDto]:
        """Pull alerts from Nagios XI API if API key is provided."""
        if not self.authentication_config.api_key:
            self.logger.warning("Nagios API Key not provided, skipping Pull.")
            return []

        alerts = []
        base_url = str(self.authentication_config.host_url).rstrip("/")

        # Get Service Status
        try:
            url = f"{base_url}/nagiosxi/api/v1/objects/servicestatus"
            params = {"apikey": self.authentication_config.api_key}
            # verify=False because many Nagios installations use self-signed certs
            response = requests.get(url, params=params, verify=False)
            response.raise_for_status()
            data = response.json()

            for service in data.get("servicestatus", []):
                if service.get("current_state") != "0":  # Only pull non-OK alerts
                    alerts.append(self._format_alert(service))
        except Exception as e:
            self.logger.error(f"Error pulling Nagios service status: {e}")

        return alerts

    @staticmethod
    def _format_alert(event: dict, provider_instance: BaseProvider = None) -> AlertDto:
        """Format Nagios event (from API or Webhook) to Keep AlertDto."""
        state = str(event.get("current_state", event.get("state", "3")))

        return AlertDto(
            id=event.get("service_id", event.get("host_id", "unknown")),
            name=event.get(
                "service_description", event.get("host_name", "Nagios Alert")
            ),
            instance_name=event.get("host_name"),
            severity=NagiosProvider.SEVERITY_MAP.get(state, AlertSeverity.INFO),
            status=NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING),
            description=event.get("status_update", event.get("output", "")),
            lastReceived=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            source=["nagios"],
            **event,  # Keep extra fields for context
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        if not self.authentication_config.api_key:
            return {"authenticated": "API Key missing"}
        try:
            base_url = str(self.authentication_config.host_url).rstrip("/")
            url = f"{base_url}/nagiosxi/api/v1/system/status"
            params = {"apikey": self.authentication_config.api_key}
            res = requests.get(url, params=params, verify=False)
            if res.ok:
                return {"authenticated": True}
            return {"authenticated": f"Failed to authenticate: {res.text}"}
        except Exception as e:
            return {"authenticated": str(e)}


if __name__ == "__main__":
    # Test code can be added here
    pass
