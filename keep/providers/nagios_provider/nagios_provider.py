"""
Nagios Provider is a class that provides a way to receive alerts from Nagios.
"""

import dataclasses
import logging
import pydantic
import requests
from keep.api.models.alert import AlertDto, AlertSeverity, AlertStatus
from keep.contextmanager.contextmanager import ContextManager
from keep.providers.base.base_provider import BaseProvider
from keep.providers.models.provider_config import ProviderConfig, ProviderScope


@pydantic.dataclasses.dataclass
class NagiosProviderAuthConfig:
    """
    Allows User Authentication with Nagios API/CGI.

    config params:
    - host_url: Base URL of Nagios instance (e.g. http://nagios.example.com/nagios)
    - api_user: Username for authentication
    - api_password: Password for authentication
    """

    host_url: pydantic.AnyHttpUrl = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Host URL",
            "hint": "e.g. http://nagios.example.com/nagios",
            "sensitive": False,
            "validation": "any_http_url",
        }
    )

    api_user: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios User",
            "sensitive": False,
        }
    )

    api_password: str = dataclasses.field(
        metadata={
            "required": True,
            "description": "Nagios Password",
            "sensitive": True,
        }
    )


class NagiosProvider(BaseProvider):
    """
    Get alerts from Nagios into Keep.

    feat:
    - Fetching alerts from Nagios services & hosts via statusjson.cgi
    - Mapping Nagios states to Keep alert status and severity
    - Supporting webhook integration for real-time alerts
    """

    PROVIDER_DISPLAY_NAME = "Nagios"
    PROVIDER_TAGS = ["alert"]
    PROVIDER_CATEGORY = ["Monitoring"]
    WEBHOOK_INSTALLATION_REQUIRED = True
    PROVIDER_ICON = "nagios-icon.png"

    # Nagios states Mapping to Keep alert states
    # 0=OK, 1=WARNING, 2=CRITICAL, 3=UNKNOWN
    STATUS_MAP = {
        0: AlertStatus.RESOLVED,
        1: AlertStatus.FIRING,
        2: AlertStatus.FIRING,
        3: AlertStatus.FIRING,
    }

    SEVERITY_MAP = {
        0: AlertSeverity.INFO,
        1: AlertSeverity.WARNING,
        2: AlertSeverity.CRITICAL,
        3: AlertSeverity.INFO,
    }

    def __init__(
        self, context_manager: ContextManager, provider_id: str, config: ProviderConfig
    ):
        super().__init__(context_manager, provider_id, config)

    def validate_config(self):
        """
        Validates required configuration for Nagios provider.
        """
        self.authentication_config = NagiosProviderAuthConfig(
            **self.config.authentication
        )

    def validate_scopes(self):
        """
        Validate provider scopes by testing connectivity.
        """
        self.logger.info("Validating Nagios provider")
        try:
            # Try to hit the status CGI
            response = requests.get(
                url=f"{self.authentication_config.host_url}/cgi-bin/statusjson.cgi?query=programstatus",
                auth=(
                    self.authentication_config.api_user,
                    self.authentication_config.api_password,
                ),
                verify=True,
            )

            if response.status_code != 200:
                response.raise_for_status()

            return {"read_alerts": True}

        except Exception as e:
            self.logger.exception("Failed to validate Nagios scopes")
            return {"read_alerts": str(e)}

    def _get_alerts(self) -> list[AlertDto]:
        """
        Get alerts from Nagios via statusjson.cgi.
        """
        self.logger.info("Getting alerts from Nagios")
        alerts = []
        try:
            # Get service status
            response = requests.get(
                url=f"{self.authentication_config.host_url}/cgi-bin/statusjson.cgi?query=servicelist",
                auth=(
                    self.authentication_config.api_user,
                    self.authentication_config.api_password,
                ),
                verify=True,
            )
            response.raise_for_status()
            data = response.json().get("data", {})
            services = data.get("servicelist", {})

            for hostname, host_services in services.items():
                for service_name, service_data in host_services.items():
                    # Only add if not OK (0)
                    status_code = service_data.get("status", 0)
                    if status_code != 0:
                        alerts.append(
                            AlertDto(
                                id=f"{hostname}-{service_name}",
                                name=service_name,
                                status=self.STATUS_MAP.get(status_code, AlertStatus.FIRING),
                                severity=self.SEVERITY_MAP.get(status_code, AlertSeverity.INFO),
                                lastReceived=None, # Nagios doesn't always provide a clean timestamp here
                                description=service_data.get("plugin_output", ""),
                                hostname=hostname,
                                source=["nagios"],
                            )
                        )
            return alerts

        except Exception as e:
            self.logger.exception("Failed to get alerts from Nagios")
            raise Exception(f"Failed to get alerts from Nagios: {str(e)}")

    @staticmethod
    def _format_alert(
        event: dict, provider_instance: "BaseProvider" = None
    ) -> AlertDto | list[AlertDto]:
        """
        Format Nagios webhook payload into Keep alert format.
        Expected payload format (sent via custom curl command in Nagios):
        {
            "host": "$HOSTNAME$",
            "service": "$SERVICEDESC$",
            "state": "$SERVICESTATE$",
            "state_id": "$SERVICESTATEID$",
            "output": "$SERVICEOUTPUT$"
        }
        """
        state_id = int(event.get("state_id", 3))
        
        alert = AlertDto(
            id=f"{event.get('host')}-{event.get('service')}",
            name=event.get("service") or event.get("host"),
            status=NagiosProvider.STATUS_MAP.get(state_id, AlertStatus.FIRING),
            severity=NagiosProvider.SEVERITY_MAP.get(state_id, AlertSeverity.INFO),
            description=event.get("output", ""),
            hostname=event.get("host"),
            source=["nagios"],
            service_name=event.get("service"),
        )
        return alert


if __name__ == "__main__":
    # Test logic
    pass
