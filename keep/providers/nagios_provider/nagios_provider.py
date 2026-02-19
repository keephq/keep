"""
Nagios Provider is a class that allows to ingest/digest data from Nagios XI.
"""

import dataclasses
import logging
from typing import List, Optional
from urllib.parse import urljoin

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
    Nagios XI authentication configuration.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI URL",
            "hint": "https://nagios.example.com/nagiosxi",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "hint": "Admin -> Manage API Keys",
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
    Pull/Push alerts from Nagios XI into Keep.
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_CATEGORY = ["Monitoring"]
    
    PROVIDER_SCOPES = [
        ProviderScope(
            name="authenticated",
            description="User is authenticated to Nagios XI API",
            mandatory=True,
            documentation_url="https://www.nagios.org/documentation/",
        ),
    ]
    
    SEVERITIES_MAP = {
        "CRITICAL": AlertSeverity.CRITICAL,
        "WARNING": AlertSeverity.WARNING,
        "UNKNOWN": AlertSeverity.INFO,
        "OK": AlertSeverity.LOW,
        "UP": AlertSeverity.LOW,
        "DOWN": AlertSeverity.CRITICAL,
        "UNREACHABLE": AlertSeverity.HIGH,
    }

    STATUS_MAP = {
        "CRITICAL": AlertStatus.FIRING,
        "WARNING": AlertStatus.FIRING,
        "UNKNOWN": AlertStatus.FIRING,
        "OK": AlertStatus.RESOLVED,
        "UP": AlertStatus.RESOLVED,
        "DOWN": AlertStatus.FIRING,
        "UNREACHABLE": AlertStatus.FIRING,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_scopes(self) -> dict[str, bool | str]:
        """Validate that we can authenticate with Nagios XI."""
        scopes = {}
        try:
            self._get_system_status()
            scopes["authenticated"] = True
        except Exception as e:
            scopes["authenticated"] = str(e)
        return scopes

    def validate_config(self):
        """Validate the provider configuration."""
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def dispose(self):
        """Dispose of the provider."""
        pass

    def _get_api_url(self, endpoint: str) -> str:
        """Build the full API URL."""
        base_url = str(self.authentication_config.nagios_url).rstrip("/")
        return f"{base_url}/api/v1/{endpoint}?apikey={self.authentication_config.api_key}&pretty=1"

    def _make_request(self, endpoint: str, params: dict = None) -> dict:
        """Make a request to the Nagios XI API."""
        url = self._get_api_url(endpoint)
        if params:
            param_str = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{url}&{param_str}"
        
        response = requests.get(
            url,
            verify=self.authentication_config.verify_ssl,
            timeout=30,
        )
        response.raise_for_status()
        return response.json()

    def _get_system_status(self) -> dict:
        """Get the Nagios XI system status."""
        return self._make_request("system/status")

    def _get_alerts(self) -> List[AlertDto]:
        """Get all current problems/alerts from Nagios XI."""
        alerts = []
        
        # Get host problems
        try:
            host_problems = self._make_request("objects/hoststatus", {
                "current_state": "in:1,2",  # DOWN or UNREACHABLE
            })
            for host in host_problems.get("hoststatus", []):
                alerts.append(self._format_host_alert(host))
        except Exception as e:
            logger.warning(f"Failed to get host problems: {e}")

        # Get service problems
        try:
            service_problems = self._make_request("objects/servicestatus", {
                "current_state": "in:1,2,3",  # WARNING, CRITICAL, or UNKNOWN
            })
            for service in service_problems.get("servicestatus", []):
                alerts.append(self._format_service_alert(service))
        except Exception as e:
            logger.warning(f"Failed to get service problems: {e}")

        return alerts

    def _format_host_alert(self, host: dict) -> AlertDto:
        """Format a Nagios host status as an AlertDto."""
        state_map = {0: "UP", 1: "DOWN", 2: "UNREACHABLE"}
        state = state_map.get(int(host.get("current_state", 0)), "UNKNOWN")
        
        return AlertDto(
            id=f"nagios-host-{host.get('host_object_id', '')}",
            name=f"Host {state}: {host.get('name', 'Unknown')}",
            description=host.get("status_text", host.get("output", "")),
            severity=self.SEVERITIES_MAP.get(state, AlertSeverity.INFO),
            status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
            source=["nagios"],
            host=host.get("name"),
            lastReceived=host.get("last_check"),
            fingerprint=f"nagios-host-{host.get('host_object_id', '')}",
        )

    def _format_service_alert(self, service: dict) -> AlertDto:
        """Format a Nagios service status as an AlertDto."""
        state_map = {0: "OK", 1: "WARNING", 2: "CRITICAL", 3: "UNKNOWN"}
        state = state_map.get(int(service.get("current_state", 0)), "UNKNOWN")
        
        return AlertDto(
            id=f"nagios-service-{service.get('service_object_id', '')}",
            name=f"Service {state}: {service.get('name', 'Unknown')} on {service.get('host_name', 'Unknown')}",
            description=service.get("status_text", service.get("output", "")),
            severity=self.SEVERITIES_MAP.get(state, AlertSeverity.INFO),
            status=self.STATUS_MAP.get(state, AlertStatus.FIRING),
            source=["nagios"],
            host=service.get("host_name"),
            service=service.get("name"),
            lastReceived=service.get("last_check"),
            fingerprint=f"nagios-service-{service.get('service_object_id', '')}",
        )

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["NagiosProvider"] = None
    ) -> AlertDto:
        """Format a Nagios webhook event as an AlertDto."""
        # Webhook payload from Nagios XI
        host_name = event.get("HOSTNAME", event.get("host_name", "Unknown"))
        service_desc = event.get("SERVICEDESC", event.get("service_description"))
        state = event.get("HOSTSTATE", event.get("SERVICESTATE", "UNKNOWN"))
        output = event.get("HOSTOUTPUT", event.get("SERVICEOUTPUT", ""))
        
        severity = NagiosProvider.SEVERITIES_MAP.get(state, AlertSeverity.INFO)
        status = NagiosProvider.STATUS_MAP.get(state, AlertStatus.FIRING)
        
        if service_desc:
            alert_id = f"nagios-{host_name}-{service_desc}"
            name = f"Service {state}: {service_desc} on {host_name}"
        else:
            alert_id = f"nagios-{host_name}"
            name = f"Host {state}: {host_name}"

        return AlertDto(
            id=alert_id,
            name=name,
            description=output,
            severity=severity,
            status=status,
            source=["nagios"],
            host=host_name,
            service=service_desc,
            fingerprint=alert_id,
            lastReceived=event.get("LONGDATETIME"),
        )

    def _get_alerts_from_api(self) -> List[AlertDto]:
        """Pull alerts from Nagios XI API."""
        return self._get_alerts()


ProvidersFactory.register_provider(NagiosProvider)
