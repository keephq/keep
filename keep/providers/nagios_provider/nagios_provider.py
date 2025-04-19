"""
Nagios Provider is a class that allows to ingest/digest data from Nagios.
"""

import dataclasses
import datetime
import json
import logging
from typing import Literal

import pydantic
import requests

from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.base.provider_exceptions import ProviderMethodException
from keep.providers.models.provider_config import ProviderConfig, ProviderScope
from keep.providers.models.provider_method import ProviderMethod

logger = logging.getLogger(__name__)


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Nagios authentication configuration.
    """

    nagios_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Web Interface URL",
            "hint": "https://nagios.example.com",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )
    username: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Username",
            "hint": "Your Nagios username",
            "sensitive": False,
        }
    )
    password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Password",
            "hint": "Your Nagios password",
            "sensitive": True,
        }
    )


class NagiosProvider(BaseProvider):
    """
    Pull/Push alerts from Nagios into Keep.
    """

    PROVIDER_CATEGORY = ["Monitoring"]
    PROVIDER_SCOPES = [
        ProviderScope(
            name="status",
            description="The method allows to retrieve service and host status.",
            mandatory=True,
            mandatory_for_webhook=False,
            documentation_url="https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/4/en/cgiapi.html",
        ),
        ProviderScope(
            name="cmd",
            description="The method allows to send commands to Nagios.",
            mandatory=True,
            mandatory_for_webhook=True,
            documentation_url="https://assets.nagios.com/downloads/nagioscore/docs/nagioscore/4/en/cgiapi.html",
        ),
    ]
    PROVIDER_METHODS = [
        ProviderMethod(
            name="Acknowledge Host",
            func_name="acknowledge_host",
            scopes=["cmd"],
            type="action",
        ),
        ProviderMethod(
            name="Acknowledge Service",
            func_name="acknowledge_service",
            scopes=["cmd"],
            type="action",
        ),
        ProviderMethod(
            name="Disable Host Checks",
            func_name="disable_host_checks",
            scopes=["cmd"],
            type="action",
        ),
        ProviderMethod(
            name="Enable Host Checks",
            func_name="enable_host_checks",
            scopes=["cmd"],
            type="action",
        ),
        ProviderMethod(
            name="Disable Service Checks",
            func_name="disable_service_checks",
            scopes=["cmd"],
            type="action",
        ),
        ProviderMethod(
            name="Enable Service Checks",
            func_name="enable_service_checks",
            scopes=["cmd"],
            type="action",
        ),
    ]

    SEVERITIES_MAP = {
        "ok": AlertSeverity.INFO,
        "warning": AlertSeverity.WARNING,
        "critical": AlertSeverity.CRITICAL,
        "unknown": AlertSeverity.HIGH,
        "down": AlertSeverity.CRITICAL,
        "up": AlertSeverity.INFO,
    }

    STATUS_MAP = {
        "ok": AlertStatus.RESOLVED,
        "warning": AlertStatus.FIRING,
        "critical": AlertStatus.FIRING,
        "unknown": AlertStatus.FIRING,
        "down": AlertStatus.FIRING,
        "up": AlertStatus.RESOLVED,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)
        self.auth_config = NagiosProviderAuthConfig(**config.authentication)

    def dispose(self):
        """
        Dispose the provider.
        """
        pass

    def acknowledge_host(self, host: str, comment: str = None):
        """
        Acknowledge a host problem.

        Args:
            host (str): The host name
            comment (str, optional): A comment about the acknowledgment
        """
        self.logger.info(f"Acknowledging host {host}")
        params = {
            "cmd_typ": "33",  # ACKNOWLEDGE_HOST_PROBLEM
            "host": host,
            "sticky_ack": "1",
            "notify": "1",
            "persistent": "1",
        }
        if comment:
            params["com_data"] = comment
        self.__send_command(params)
        self.logger.info(f"Acknowledged host {host}")

    def acknowledge_service(self, host: str, service: str, comment: str = None):
        """
        Acknowledge a service problem.

        Args:
            host (str): The host name
            service (str): The service name
            comment (str, optional): A comment about the acknowledgment
        """
        self.logger.info(f"Acknowledging service {service} on host {host}")
        params = {
            "cmd_typ": "34",  # ACKNOWLEDGE_SVC_PROBLEM
            "host": host,
            "service": service,
            "sticky_ack": "1",
            "notify": "1",
            "persistent": "1",
        }
        if comment:
            params["com_data"] = comment
        self.__send_command(params)
        self.logger.info(f"Acknowledged service {service} on host {host}")

    def disable_host_checks(self, host: str):
        """
        Disable active checks for a host.

        Args:
            host (str): The host name
        """
        self.logger.info(f"Disabling checks for host {host}")
        params = {
            "cmd_typ": "1",  # DISABLE_HOST_CHECK
            "host": host,
        }
        self.__send_command(params)
        self.logger.info(f"Disabled checks for host {host}")

    def enable_host_checks(self, host: str):
        """
        Enable active checks for a host.

        Args:
            host (str): The host name
        """
        self.logger.info(f"Enabling checks for host {host}")
        params = {
            "cmd_typ": "2",  # ENABLE_HOST_CHECK
            "host": host,
        }
        self.__send_command(params)
        self.logger.info(f"Enabled checks for host {host}")

    def disable_service_checks(self, host: str, service: str):
        """
        Disable active checks for a service.

        Args:
            host (str): The host name
            service (str): The service name
        """
        self.logger.info(f"Disabling checks for service {service} on host {host}")
        params = {
            "cmd_typ": "3",  # DISABLE_SVC_CHECK
            "host": host,
            "service": service,
        }
        self.__send_command(params)
        self.logger.info(f"Disabled checks for service {service} on host {host}")

    def enable_service_checks(self, host: str, service: str):
        """
        Enable active checks for a service.

        Args:
            host (str): The host name
            service (str): The service name
        """
        self.logger.info(f"Enabling checks for service {service} on host {host}")
        params = {
            "cmd_typ": "4",  # ENABLE_SVC_CHECK
            "host": host,
            "service": service,
        }
        self.__send_command(params)
        self.logger.info(f"Enabled checks for service {service} on host {host}")

    def validate_config(self):
        """
        Validates the provider configuration.
        """
        self.authentication_config = NagiosProviderAuthConfig(**self.config.authentication)

    def validate_scopes(self) -> dict[str, bool | str]:
        """
        Validates the provider scopes.
        """
        return {
            "status": True,
            "cmd": True,
        }

    def __send_command(self, params: dict):
        """
        Send a command to Nagios.

        Args:
            params (dict): The command parameters
        """
        try:
            response = requests.post(
                f"{self.auth_config.nagios_url}/cgi-bin/cmd.cgi",
                params=params,
                auth=(self.auth_config.username, self.auth_config.password),
                verify=True,
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise ProviderMethodException(f"Failed to send command to Nagios: {str(e)}")

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from Nagios.

        Returns:
            list[AlertDto]: List of alerts
        """
        try:
            # Get host status
            host_response = requests.get(
                f"{self.auth_config.nagios_url}/cgi-bin/statusjson.cgi",
                params={"query": "hostlist"},
                auth=(self.auth_config.username, self.auth_config.password),
                verify=True,
            )
            host_response.raise_for_status()
            host_data = host_response.json()

            # Get service status
            service_response = requests.get(
                f"{self.auth_config.nagios_url}/cgi-bin/statusjson.cgi",
                params={"query": "servicelist"},
                auth=(self.auth_config.username, self.auth_config.password),
                verify=True,
            )
            service_response.raise_for_status()
            service_data = service_response.json()

            alerts = []

            # Process host alerts
            for host_name, host_info in host_data.get("data", {}).get("hostlist", {}).items():
                status = host_info.get("status", "").lower()
                if status in ["down", "up"]:
                    alerts.append(
                        AlertDto(
                            id=f"host_{host_name}",
                            name=f"Host {host_name} is {status}",
                            status=self.STATUS_MAP.get(status, AlertStatus.FIRING),
                            severity=self.SEVERITIES_MAP.get(status, AlertSeverity.INFO),
                            source=["nagios"],
                            raw=host_info,
                        )
                    )

            # Process service alerts
            for host_name, services in service_data.get("data", {}).get("servicelist", {}).items():
                for service_name, service_info in services.items():
                    status = service_info.get("status", "").lower()
                    if status in ["ok", "warning", "critical", "unknown"]:
                        alerts.append(
                            AlertDto(
                                id=f"service_{host_name}_{service_name}",
                                name=f"Service {service_name} on {host_name} is {status}",
                                status=self.STATUS_MAP.get(status, AlertStatus.FIRING),
                                severity=self.SEVERITIES_MAP.get(status, AlertSeverity.INFO),
                                source=["nagios"],
                                raw=service_info,
                            )
                        )

            return alerts

        except requests.exceptions.RequestException as e:
            raise ProviderMethodException(f"Failed to get alerts from Nagios: {str(e)}")

    @staticmethod
    def _format_alert(
        alert: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto:
        """
        Format a Nagios alert into a Keep alert.

        Args:
            alert (dict): The Nagios alert
            provider_instance (BaseProvider, optional): The provider instance

        Returns:
            AlertDto: The formatted alert
        """
        return AlertDto(
            id=alert.get("id"),
            name=alert.get("name"),
            status=alert.get("status"),
            severity=alert.get("severity"),
            source=["nagios"],
            raw=alert.get("raw"),
        ) 