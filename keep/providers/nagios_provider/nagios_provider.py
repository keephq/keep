"""
Nagios is a class that provides a set of methods to interact with the Nagios API.
Nagios is an open-source monitoring system that monitors hosts and services.
https://www.nagios.org/
"""

import dataclasses
import datetime

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
    NagiosProviderAuthConfig is a class that holds the authentication information for the NagiosProvider.
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL (e.g., http://nagios.example.com)",
            "sensitive": False,
            "validation": "any_http_url",
        },
    )

    api_token: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios API Token",
            "sensitive": True,
        },
        default=None,
    )

    username: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios Username (for basic auth)",
            "sensitive": False,
        },
        default=None,
    )

    password: str = dataclasses.field(
        metadata={
            "required": False,
            "description": "Nagios Password (for basic auth)",
            "sensitive": True,
        },
        default=None,
    )


class NagiosProvider(BaseProvider):
    """
    Nagios provider for Keep.
    
    This provider integrates with Nagios Core and Nagios XI to fetch
    host and service alerts/alerts.
    
    Nagios Status Codes:
    - Host: UP (0), DOWN (2), UNREACHABLE (3)
    - Service: OK (0), WARNING (1), CRITICAL (2), UNKNOWN (3)
    
    Reference: https://www.nagios.org/
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(name="authenticated", description="User is authenticated"),
    ]

    # Nagios host status mapping
    # 0 = UP, 2 = DOWN, 3 = UNREACHABLE
    HOST_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }

    # Nagios service status mapping
    # 0 = OK, 1 = WARNING, 2 = CRITICAL, 3 = UNKNOWN
    SERVICE_STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }

    # Severity mapping based on Nagios states
    HOST_SEVERITY_MAP = {
        0: AlertSeverity.LOW,  # UP
        2: AlertSeverity.CRITICAL,  # DOWN
        3: AlertSeverity.WARNING,  # UNREACHABLE
    }

    SERVICE_SEVERITY_MAP = {
        0: AlertSeverity.LOW,  # OK
        1: AlertSeverity.WARNING,  # WARNING
        2: AlertSeverity.CRITICAL,  # CRITICAL
        3: AlertSeverity.INFO,  # UNKNOWN
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def dispose(self):
        """
        Dispose provider resources.
        """
        pass

    def validate_config(self):
        """
        Validates the configuration of the Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def __get_base_url(self) -> str:
        """
        Get the base URL for Nagios API.
        """
        url = str(self.authentication_config.host_url).rstrip("/")
        return url

    def __get_headers(self) -> dict:
        """
        Get headers for Nagios API requests.
        """
        headers = {
            "Content-Type": "application/json",
        }
        if self.authentication_config.api_token:
            headers["Authorization"] = f"Bearer {self.authentication_config.api_token}"
        return headers

    def __get_auth(self) -> tuple | None:
        """
        Get basic auth tuple if username/password are provided.
        """
        if self.authentication_config.username and self.authentication_config.password:
            return (self.authentication_config.username, self.authentication_config.password)
        return None

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validate the scopes of the provider.
        """
        try:
            # Try to get host status as a validation check
            url = f"{self.__get_base_url()}/nagios/cgi-bin/statusjson.cgi?query=hostlist"
            response = requests.get(
                url,
                headers=self.__get_headers(),
                auth=self.__get_auth(),
                timeout=30,
            )
            if response.ok:
                scopes = {"authenticated": True}
            else:
                scopes = {
                    "authenticated": f"Error validating scopes: {response.status_code} {response.text}"
                }
        except Exception as e:
            scopes = {
                "authenticated": f"Error validating scopes: {e}",
            }

        return scopes

    def __get_host_alerts(self) -> list[AlertDto]:
        """
        Get host alerts from Nagios.
        """
        try:
            # Try Nagios XI API first, fallback to Core API
            url = f"{self.__get_base_url()}/nagiosxi/api/v1/objects/hoststatus"
            
            params = {}
            if self.authentication_config.api_token:
                params["apikey"] = self.authentication_config.api_token
            
            response = requests.get(
                url,
                headers=self.__get_headers(),
                auth=self.__get_auth(),
                params=params,
                timeout=30,
            )

            # If Nagios XI API fails, try Core JSON CGI
            if not response.ok:
                url = f"{self.__get_base_url()}/nagios/cgi-bin/statusjson.cgi?query=servicelist&details=true"
                response = requests.get(
                    url,
                    headers=self.__get_headers(),
                    auth=self.__get_auth(),
                    timeout=30,
                )

            if not response.ok:
                self.logger.error(
                    "Failed to get host status from Nagios: %s", response.text
                )
                raise ProviderException(f"Failed to get host status from Nagios: {response.status_code}")

            data = response.json()
            
            # Parse Nagios XI response format
            if "hoststatus" in data:
                host_list = data["hoststatus"]
            elif "data" in data and "hostlist" in data["data"]:
                host_list = data["data"]["hostlist"]
            else:
                host_list = []

            alerts = []
            for host in host_list:
                # Handle different response formats
                if isinstance(host, dict):
                    host_name = host.get("name") or host.get("host_name") or "Unknown"
                    current_state = host.get("current_state") or host.get("status") or 0
                    plugin_output = host.get("plugin_output") or host.get("output") or ""
                    last_check = host.get("last_check") or host.get("last_check_time") or 0
                    
                    # Map status to Keep format
                    status = self.HOST_STATUS_MAP.get(int(current_state), AlertStatus.FIRING)
                    severity = self.HOST_SEVERITY_MAP.get(int(current_state), AlertSeverity.WARNING)
                    
                    # Parse timestamp
                    try:
                        if isinstance(last_check, (int, float)):
                            last_received = datetime.datetime.fromtimestamp(
                                last_check, tz=datetime.timezone.utc
                            ).isoformat()
                        else:
                            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    except:
                        last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

                    alert = AlertDto(
                        id=f"nagios-host-{host_name}",
                        fingerprint=f"nagios-host-{host_name}",
                        name=host_name,
                        description=plugin_output,
                        status=status,
                        severity=severity,
                        lastReceived=last_received,
                        source=["nagios"],
                        host_name=host_name,
                        current_state=current_state,
                        acknowledged=host.get("acknowledged", False),
                        comments=host.get("comments", []),
                    )
                    alerts.append(alert)

            return alerts

        except Exception as e:
            self.logger.error("Error getting host alerts from Nagios: %s", e)
            raise ProviderException(f"Error getting host alerts from Nagios: {e}") from e

    def __get_service_alerts(self) -> list[AlertDto]:
        """
        Get service alerts from Nagios.
        """
        try:
            # Try Nagios XI API first
            url = f"{self.__get_base_url()}/nagiosxi/api/v1/objects/servicestatus"
            
            params = {}
            if self.authentication_config.api_token:
                params["apikey"] = self.authentication_config.api_token
            
            response = requests.get(
                url,
                headers=self.__get_headers(),
                auth=self.__get_auth(),
                params=params,
                timeout=30,
            )

            # If Nagios XI API fails, try Core JSON CGI
            if not response.ok:
                url = f"{self.__get_base_url()}/nagios/cgi-bin/statusjson.cgi?query=servicelist&details=true"
                response = requests.get(
                    url,
                    headers=self.__get_headers(),
                    auth=self.__get_auth(),
                    timeout=30,
                )

            if not response.ok:
                self.logger.error(
                    "Failed to get service status from Nagios: %s", response.text
                )
                raise ProviderException(f"Failed to get service status from Nagios: {response.status_code}")

            data = response.json()
            
            # Parse Nagios XI response format
            if "servicestatus" in data:
                service_list = data["servicestatus"]
            elif "data" in data and "servicelist" in data["data"]:
                service_list = data["data"]["servicelist"]
            else:
                service_list = []

            alerts = []
            for service in service_list:
                if isinstance(service, dict):
                    host_name = service.get("host_name") or service.get("host") or "Unknown"
                    service_name = service.get("service_description") or service.get("name") or "Unknown"
                    current_state = service.get("current_state") or service.get("status") or 0
                    plugin_output = service.get("plugin_output") or service.get("output") or ""
                    last_check = service.get("last_check") or service.get("last_check_time") or 0
                    
                    # Map status to Keep format
                    status = self.SERVICE_STATUS_MAP.get(int(current_state), AlertStatus.FIRING)
                    severity = self.SERVICE_SEVERITY_MAP.get(int(current_state), AlertSeverity.WARNING)
                    
                    # Parse timestamp
                    try:
                        if isinstance(last_check, (int, float)):
                            last_received = datetime.datetime.fromtimestamp(
                                last_check, tz=datetime.timezone.utc
                            ).isoformat()
                        else:
                            last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()
                    except:
                        last_received = datetime.datetime.now(datetime.timezone.utc).isoformat()

                    alert = AlertDto(
                        id=f"nagios-service-{host_name}-{service_name}",
                        fingerprint=f"nagios-service-{host_name}-{service_name}",
                        name=f"{host_name}/{service_name}",
                        description=plugin_output,
                        status=status,
                        severity=severity,
                        lastReceived=last_received,
                        source=["nagios"],
                        host_name=host_name,
                        service_name=service_name,
                        current_state=current_state,
                        acknowledged=service.get("acknowledged", False),
                        comments=service.get("comments", []),
                    )
                    alerts.append(alert)

            return alerts

        except Exception as e:
            self.logger.error("Error getting service alerts from Nagios: %s", e)
            raise ProviderException(f"Error getting service alerts from Nagios: {e}") from e

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get all alerts from Nagios (hosts and services).
        """
        alerts = []
        
        try:
            self.logger.info("Collecting host alerts from Nagios")
            host_alerts = self.__get_host_alerts()
            alerts.extend(host_alerts)
        except Exception as e:
            self.logger.error("Error getting host alerts from Nagios: %s", e)

        try:
            self.logger.info("Collecting service alerts from Nagios")
            service_alerts = self.__get_service_alerts()
            alerts.extend(service_alerts)
        except Exception as e:
            self.logger.error("Error getting service alerts from Nagios: %s", e)

        return alerts


if __name__ == "__main__":
    import logging

    logging.basicConfig(level=logging.DEBUG, handlers=[logging.StreamHandler()])
    context_manager = ContextManager(
        tenant_id="singletenant",
        workflow_id="test",
    )

    import os

    host_url = os.environ.get("NAGIOS_HOST_URL")
    api_token = os.environ.get("NAGIOS_API_TOKEN")
    username = os.environ.get("NAGIOS_USERNAME")
    password = os.environ.get("NAGIOS_PASSWORD")

    if host_url is None:
        raise ProviderException("NAGIOS_HOST_URL is not set")

    config = ProviderConfig(
        description="Nagios Provider",
        authentication={
            "host_url": host_url,
            "api_token": api_token,
            "username": username,
            "password": password,
        },
    )

    provider = NagiosProvider(
        context_manager,
        provider_id="nagios",
        config=config,
    )

    provider._get_alerts()
