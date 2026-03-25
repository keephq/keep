"""
Nagios Provider is a class that allows to ingest/digest data from Nagios.
"""

import dataclasses
import datetime
import json
import logging
from typing import Union

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.providers_factory import ProvidersFactory

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL",
            "hint": "https://nagios.example.com/nagios",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios API Username",
            "hint": "nagiosadmin",
            "sensitive": False,
        }
    )
    api_password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios API Password",
            "hint": "********",
            "sensitive": True,
        }
    )
    verify_ssl: bool = dataclasses.field(
        metadata={
            "description": "Verify SSL certificates",
            "hint": "Set to false for self-signed certificates",
            "sensitive": False,
        },
        default=True,
    )


class NagiosProvider(BaseProvider):
    """
    Pull alerts from Nagios into Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]

    PROVIDER_SCOPES = [
        ProviderScope(
            name="status",
            description="Read access to Nagios status and alerts",
            mandatory=True,
            mandatory_for_webhook=True,
        ),
    ]

    SEVERITY_MAP = {
        "OK": AlertSeverity.LOW,
        "WARNING": AlertSeverity.WARNING,
        "CRITICAL": AlertSeverity.CRITICAL,
        "UNKNOWN": AlertSeverity.HIGH,
        "UP": AlertSeverity.LOW,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.WARNING,
    }

    STATUS_MAP = {
        "OK": AlertStatus.RESOLVED,
        "WARNING": AlertStatus.WARNING,
        "CRITICAL": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.PENDING,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.WARNING,
    }

    def __init__(
        self,
        context_manager: ContextManager,
        provider_id: str,
        config: ProviderConfig,
    ):
        super().__init__(context_manager, provider_id, config)
        self._host_url = self.config.authentication.get("host_url", "").rstrip("/")
        self._auth = (
            self.config.authentication.get("api_username"),
            self.config.authentication.get("api_password"),
        )
        self._verify = self.config.authentication.get("verify_ssl", True)

    def dispose(self):
        pass

    def validate_config(self):
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self) -> dict[str, bool | str]:
        try:
            response = requests.get(
                f"{self._host_url}/cgi-bin/status.cgi?hostgroup=all&style=summary&jsonoutput",
                auth=self._auth,
                verify=self._verify,
                timeout=10,
            )
            if response.status_code == 200:
                return {"status": True}
            return {"status": f"HTTP {response.status_code}: {response.text[:100]}"}
        except Exception as e:
            return {"status": str(e)}

    def __send_request(self, endpoint: str, params: dict = None) -> dict:
        """Send a request to the Nagios API."""
        url = f"{self._host_url}/cgi-bin/{endpoint}"
        default_params = {"jsonoutput": ""}
        if params:
            default_params.update(params)

        response = requests.get(
            url,
            params=default_params,
            auth=self._auth,
            verify=self._verify,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _convert_severity(state: str) -> AlertSeverity:
        """Convert Nagios state to Keep severity."""
        return NagiosProvider.SEVERITY_MAP.get(
            state.upper() if state else "UNKNOWN",
            AlertSeverity.HIGH,
        )

    @staticmethod
    def _convert_status(state: str) -> AlertStatus:
        """Convert Nagios state to Keep alert status."""
        return NagiosProvider.STATUS_MAP.get(
            state.upper() if state else "UNKNOWN",
            AlertStatus.PENDING,
        )

    def _get_alerts(self) -> list[AlertDto]:
        """
        Pull alerts from Nagios.
        Fetches both host and service problems.
        """
        alerts = []

        # Fetch service problems
        try:
            service_data = self.__send_request(
                "status.cgi",
                {"hostgroup": "all", "style": "detail", "servicestatustypes": "28"},
            )
            service_status = (
                service_data.get("status", {})
                .get("service_status", [])
            )
            if isinstance(service_status, list):
                for svc in service_status:
                    host_name = svc.get("host", "unknown")
                    service_name = svc.get("service", "unknown")
                    state = svc.get("status", "UNKNOWN")
                    last_check = svc.get("last_check", "")
                    duration = svc.get("duration", "")
                    attempt = svc.get("attempts", "")
                    status_info = svc.get("status_information", "")

                    alert = AlertDto(
                        id=f"{host_name}:{service_name}",
                        name=f"{service_name} on {host_name}",
                        status=self._convert_status(state),
                        severity=self._convert_severity(state),
                        lastReceived=datetime.datetime.utcnow().isoformat(),
                        source=["nagios"],
                        message=status_info,
                        description=status_info,
                        fingerprints=[f"{host_name}:{service_name}"],
                    )
                    alerts.append(alert)
        except Exception as e:
            logger.error(f"Error fetching Nagios service alerts: {e}")

        # Fetch host problems
        try:
            host_data = self.__send_request(
                "status.cgi",
                {"hostgroup": "all", "style": "detail", "hoststatustypes": "12"},
            )
            host_status = (
                host_data.get("status", {})
                .get("host_status", [])
            )
            if isinstance(host_status, list):
                for host in host_status:
                    host_name = host.get("host", "unknown")
                    state = host.get("status", "UNKNOWN")
                    status_info = host.get("status_information", "")

                    alert = AlertDto(
                        id=f"{host_name}:_host_",
                        name=f"Host {host_name} is {state}",
                        status=self._convert_status(state),
                        severity=self._convert_severity(state),
                        lastReceived=datetime.datetime.utcnow().isoformat(),
                        source=["nagios"],
                        message=status_info,
                        description=status_info,
                        fingerprints=[f"{host_name}:_host_"],
                    )
                    alerts.append(alert)
        except Exception as e:
            logger.error(f"Error fetching Nagios host alerts: {e}")

        return alerts


if __name__ == "__main__":
    import os

    # Test configuration
    config = ProviderConfig(
        authentication={
            "host_url": os.environ.get("NAGIOS_HOST", "https://nagios.example.com/nagios"),
            "api_username": os.environ.get("NAGIOS_USER", "nagiosadmin"),
            "api_password": os.environ.get("NAGIOS_PASS", ""),
        }
    )

    context_manager = ContextManager(
        tenant_id="test",
        workflow_id="test",
    )

    provider = NagiosProvider(
        context_manager=context_manager,
        provider_id="nagios-test",
        config=config,
    )

    # Validate scopes
    scopes = provider.validate_scopes()
    print(f"Scopes: {scopes}")

    # Get alerts
    if scopes.get("status"):
        alerts = provider.get_alerts()
        print(f"Found {len(alerts)} alerts:")
        for alert in alerts:
            print(f"  [{alert.severity}] {alert.name}: {alert.message}")
