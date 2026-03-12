"""
NagiosProvider is a class that provides methods to interact with the Nagios XI API.
"""

import dataclasses
import datetime
from typing import Optional

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.exceptions.provider_exception import ProviderException
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    NagiosProviderAuthConfig holds the authentication information for the NagiosProvider.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI Host URL (e.g., https://nagios.example.com)",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    api_key: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios XI API Key",
            "sensitive": True,
        },
        default=None,
    )


class NagiosProvider(BaseProvider):
    """
    NagiosProvider allows Keep to integrate with Nagios XI for monitoring alerts.
    
    Nagios is one of the most widely used open-source monitoring systems,
    providing comprehensive monitoring of hosts, services, and network infrastructure.
    """
    
    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(name="authenticated", description="User is authenticated"),
    ]

    # Nagios host states: 0=UP, 1=DOWN, 2=UNREACHABLE
    HOST_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
    }

    # Nagios service states: 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    SERVICE_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        0: AlertSeverity.LOW,      # OK
        1: AlertSeverity.WARNING,  # WARNING
        2: AlertSeverity.CRITICAL, # CRITICAL
        3: AlertSeverity.INFO,     # UNKNOWN
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        pass

    def validate_config(self):
        """
        Validates the configuration of the Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def _get_api_url(self, endpoint: str) -> str:
        """
        Constructs the full API URL for a given endpoint.
        """
        base_url = str(self.authentication_config.host_url).rstrip("/")
        return f"{base_url}/nagiosxi/api/v1/{endpoint}"

    def _make_request(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """
        Makes an authenticated request to the Nagios XI API.
        """
        url = self._get_api_url(endpoint)
        request_params = {"apikey": self.authentication_config.api_key}
        if params:
            request_params.update(params)
        
        try:
            response = requests.get(url, params=request_params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise ProviderException(f"Failed to connect to Nagios API: {str(e)}")

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider by testing API connectivity.
        """
        try:
            # Test API access by fetching system status
            self._make_request("system/status")
            return {"authenticated": True}
        except ProviderException as e:
            return {"authenticated": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Fetches current alerts from Nagios XI.
        """
        alerts = []
        
        # Fetch host problems
        try:
            host_data = self._make_request("objects/hoststatus", {"hoststatustypes": "12"})
            hosts = host_data.get("hoststatus", [])
            
            for host in hosts:
                alert = self._host_to_alert(host)
                if alert:
                    alerts.append(alert)
        except ProviderException:
            self.logger.warning("Failed to fetch host status from Nagios")

        # Fetch service problems
        try:
            service_data = self._make_request("objects/servicestatus", {"servicestatustypes": "28"})
            services = service_data.get("servicestatus", [])
            
            for service in services:
                alert = self._service_to_alert(service)
                if alert:
                    alerts.append(alert)
        except ProviderException:
            self.logger.warning("Failed to fetch service status from Nagios")

        return alerts

    def _host_to_alert(self, host: dict) -> Optional[AlertDto]:
        """
        Converts a Nagios host status to an AlertDto.
        """
        try:
            current_state = int(host.get("current_state", 0))
            
            return AlertDto(
                id=f"nagios-host-{host.get('host_id', '')}",
                name=f"Host: {host.get('name', 'Unknown')}",
                description=host.get("status_text", host.get("plugin_output", "")),
                status=self.HOST_STATUS_MAP.get(current_state, AlertStatus.FIRING),
                severity=self.SEVERITY_MAP.get(current_state, AlertSeverity.WARNING),
                source=["nagios"],
                lastReceived=datetime.datetime.fromisoformat(
                    host.get("last_check", datetime.datetime.now().isoformat())
                ) if host.get("last_check") else datetime.datetime.now(),
                fingerprint=f"nagios-host-{host.get('host_id', '')}",
                labels={
                    "host_name": host.get("name", ""),
                    "address": host.get("address", ""),
                    "host_id": str(host.get("host_id", "")),
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to convert host to alert: {e}")
            return None

    def _service_to_alert(self, service: dict) -> Optional[AlertDto]:
        """
        Converts a Nagios service status to an AlertDto.
        """
        try:
            current_state = int(service.get("current_state", 0))
            host_name = service.get("host_name", "Unknown")
            service_name = service.get("name", service.get("service_description", "Unknown"))
            
            return AlertDto(
                id=f"nagios-service-{service.get('servicestatus_id', '')}",
                name=f"Service: {host_name}/{service_name}",
                description=service.get("status_text", service.get("plugin_output", "")),
                status=self.SERVICE_STATUS_MAP.get(current_state, AlertStatus.FIRING),
                severity=self.SEVERITY_MAP.get(current_state, AlertSeverity.WARNING),
                source=["nagios"],
                lastReceived=datetime.datetime.fromisoformat(
                    service.get("last_check", datetime.datetime.now().isoformat())
                ) if service.get("last_check") else datetime.datetime.now(),
                fingerprint=f"nagios-service-{service.get('servicestatus_id', '')}",
                labels={
                    "host_name": host_name,
                    "service_name": service_name,
                    "service_id": str(service.get("servicestatus_id", "")),
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to convert service to alert: {e}")
            return None

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: Optional["NagiosProvider"] = None
    ) -> AlertDto:
        """
        Formats an incoming Nagios webhook event to AlertDto.
        
        This method handles webhooks from Nagios XI when configured to send
        notifications to Keep.
        """
        # Determine if this is a host or service alert
        is_service = "service" in event or "servicedesc" in event
        
        if is_service:
            # Service alert
            state = int(event.get("servicestate", event.get("state", 0)))
            status = NagiosProvider.SERVICE_STATUS_MAP.get(state, AlertStatus.FIRING)
            severity = NagiosProvider.SEVERITY_MAP.get(state, AlertSeverity.WARNING)
            
            host_name = event.get("hostname", event.get("host", "Unknown"))
            service_name = event.get("servicedesc", event.get("service", "Unknown"))
            
            return AlertDto(
                id=event.get("id", f"nagios-{host_name}-{service_name}"),
                name=f"Service: {host_name}/{service_name}",
                description=event.get("output", event.get("message", "")),
                status=status,
                severity=severity,
                source=["nagios"],
                fingerprint=f"nagios-service-{host_name}-{service_name}",
                labels={
                    "host_name": host_name,
                    "service_name": service_name,
                    "notification_type": event.get("notificationtype", ""),
                },
            )
        else:
            # Host alert
            state = int(event.get("hoststate", event.get("state", 0)))
            status = NagiosProvider.HOST_STATUS_MAP.get(state, AlertStatus.FIRING)
            severity = NagiosProvider.SEVERITY_MAP.get(state, AlertSeverity.WARNING)
            
            host_name = event.get("hostname", event.get("host", "Unknown"))
            
            return AlertDto(
                id=event.get("id", f"nagios-host-{host_name}"),
                name=f"Host: {host_name}",
                description=event.get("output", event.get("message", "")),
                status=status,
                severity=severity,
                source=["nagios"],
                fingerprint=f"nagios-host-{host_name}",
                labels={
                    "host_name": host_name,
                    "address": event.get("hostaddress", event.get("address", "")),
                    "notification_type": event.get("notificationtype", ""),
                },
            )


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    config = ProviderConfig(
        authentication={
            "host_url": "https://nagios.example.com",
            "api_key": "your-api-key",
        }
    )
    
    context_manager = ContextManager(tenant_id="test")
    provider = NagiosProvider(context_manager, "nagios-test", config)
    print("Nagios provider initialized successfully!")
